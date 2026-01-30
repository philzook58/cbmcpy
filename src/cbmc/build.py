from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from .ir import GotoFunctionDef, SourceLocation
from .parse import load_json, strip_json_ui, dump_json
from .parse import _run_command as _run_command


def run_cbmc(
    function_def: GotoFunctionDef,
    *,
    output_dir: str | None = None,
    goto_cc: str = "goto-cc",
    goto_instrument: str = "goto-instrument",
    symtab2gb: str = "symtab2gb",
) -> Path:
    if output_dir is None:
        out_dir = Path(tempfile.mkdtemp(prefix="cbmc_"))
    else:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    c_path = out_dir / f"{function_def.name}_stub.c"
    _write_stub_c(function_def, c_path)

    gb_path = out_dir / f"{function_def.name}_stub.gb"
    symtab_path = out_dir / f"{function_def.name}_symbol_table.json"
    functions_path = out_dir / f"{function_def.name}_goto_functions.json"

    _run_command([goto_cc, str(c_path), "-o", str(gb_path)])
    _run_command(
        [goto_instrument, "--show-symbol-table", "--json-ui", str(gb_path)],
        stdout_path=symtab_path,
    )
    _run_command(
        [goto_instrument, "--show-goto-functions", "--json-ui", str(gb_path)],
        stdout_path=functions_path,
    )

    symtab_payload = strip_json_ui(load_json(str(symtab_path)), key="symbolTable")
    functions_payload = strip_json_ui(load_json(str(functions_path)), key="functions")

    updated_functions = _replace_function_body(functions_payload, function_def, c_path)

    symtab_stripped = out_dir / f"{function_def.name}_symbol_table_stripped.json"
    functions_stripped = out_dir / f"{function_def.name}_goto_functions_stripped.json"
    dump_json(str(symtab_stripped), symtab_payload)
    dump_json(str(functions_stripped), updated_functions)

    out_gb = out_dir / f"{function_def.name}_from_json.gb"
    _run_command(
        [
            symtab2gb,
            "--goto-functions",
            str(functions_stripped),
            "--out",
            str(out_gb),
            str(symtab_stripped),
        ]
    )

    return out_gb


def _write_stub_c(function_def: GotoFunctionDef, c_path: Path) -> None:
    params = ", ".join(f"{param.typ.to_c()} {param.name}" for param in function_def.params)
    ret_type = function_def.return_type.to_c()
    stub = (
        f"{ret_type} {function_def.name}({params})" "\n"
        "{\n"
        "  return 0;\n"
        "}\n"
    )
    c_path.write_text(stub, encoding="utf-8")


def _replace_function_body(
    functions_payload: dict[str, Any],
    function_def: GotoFunctionDef,
    c_path: Path,
) -> dict[str, Any]:
    functions = functions_payload.get("functions")
    if not isinstance(functions, list):
        raise ValueError("Invalid goto-functions payload")

    updated: list[dict[str, Any]] = []
    found = False

    for fn in functions:
        if not isinstance(fn, dict):
            updated.append(fn)
            continue
        if fn.get("name") != function_def.name:
            updated.append(fn)
            continue
        found = True
        patched = dict(fn)
        patched["parameterIdentifiers"] = function_def.parameter_identifiers()
        patched["isBodyAvailable"] = True
        source_location = _select_source_location(fn, c_path, function_def.name)
        patched["instructions"] = _patch_set_return_value(
            fn.get("instructions"),
            function_def,
            source_location,
        )
        updated.append(patched)

    if not found:
        raise ValueError(f"Function '{function_def.name}' not found in template")

    return {"functions": updated}


def _select_source_location(template_fn: dict[str, Any], c_path: Path, function_name: str) -> SourceLocation:
    instructions = template_fn.get("instructions")
    if isinstance(instructions, list) and instructions:
        first = instructions[0]
        if isinstance(first, dict) and "sourceLocation" in first:
            loc = first["sourceLocation"]
            return SourceLocation(
                file=str(loc.get("file", c_path)),
                function=str(loc.get("function", function_name)),
                line=str(loc.get("line", "1")),
                working_directory=loc.get("workingDirectory"),
            )

    return SourceLocation(file=str(c_path), function=function_name, line="1", working_directory=str(c_path.parent))


def _patch_set_return_value(
    instructions: Any,
    function_def: GotoFunctionDef,
    source_location: SourceLocation,
) -> list[dict[str, Any]]:
    if not isinstance(instructions, list):
        raise ValueError("Template function is missing instructions")

    patched: list[dict[str, Any]] = []
    replaced = False
    for instr in instructions:
        if not isinstance(instr, dict):
            patched.append(instr)
            continue
        if instr.get("instructionId") != "SET_RETURN_VALUE":
            patched.append(instr)
            continue
        if not function_def.body:
            raise ValueError("Function body is empty")
        return_value = function_def.body[0].value.to_json(function_name=function_def.name)
        return_code = {
            "id": "code",
            "namedSub": {
                "statement": {"id": "return"},
                "type": {"id": "empty"},
            },
            "sub": [return_value],
        }
        updated = dict(instr)
        updated["code"] = return_code
        updated["sourceLocation"] = source_location.to_json()
        patched.append(updated)
        replaced = True

    if not replaced:
        raise ValueError("SET_RETURN_VALUE instruction not found in template")

    return patched
