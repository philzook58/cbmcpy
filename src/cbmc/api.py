from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import subprocess
import tempfile

from .ir import (
    Assign,
    Assert,
    Constant,
    Decl,
    EndFunction,
    Expr,
    FunctionType,
    GotoFunctionDef,
    SetReturnValue,
    SignedBVType,
    SourceLocation,
    Type,
    Var,
    EmptyType,
)
from .parse import dump_json
from .symtab import SymbolTableBuilder


@dataclass(frozen=True)
class GotoFunction:
    body: list
    name: str = "main"
    return_type: Type = SignedBVType(32)

    def to_def(self) -> GotoFunctionDef:
        return GotoFunctionDef(
            name=self.name,
            params=[],
            return_type=self.return_type,
            body=self.body,
        )


def verify(
    program: GotoFunction | GotoFunctionDef,
    *,
    show_output: bool = True,
    normalize: bool = True,
    symtab_builder: SymbolTableBuilder | None = None,
    cbmc_args: list[str] | None = None,
    extra_functions: Iterable[GotoFunctionDef] | None = None,
) -> subprocess.CompletedProcess:
    if isinstance(program, GotoFunction):
        function_def = program.to_def()
    else:
        function_def = program

    body = function_def.body
    if normalize:
        body = _normalize_body(function_def.body, function_def)
    function_def = GotoFunctionDef(
        name=function_def.name,
        params=function_def.params,
        return_type=function_def.return_type,
        body=body,
    )

    loc = SourceLocation(file="<generated>", function=function_def.name, line="1")
    if symtab_builder is None:
        symtab_builder = _build_symtab(function_def, loc)
    init_def = _init_function_def()
    if "__CPROVER_initialize" not in symtab_builder.symbols:
        symtab_builder.add_function(
            "__CPROVER_initialize",
            FunctionType(parameters=[], return_type=EmptyType()),
            loc,
        )

    with tempfile.TemporaryDirectory(prefix="cbmc_") as tmp_dir:
        symtab_path = Path(tmp_dir) / "symtab.json"
        functions_path = Path(tmp_dir) / "functions.json"
        gb_path = Path(tmp_dir) / "program.gb"

        dump_json(str(symtab_path), symtab_builder.to_payload())
        functions_payload = [init_def]
        if extra_functions:
            functions_payload.extend(extra_functions)
        functions_payload.append(function_def)
        dump_json(
            str(functions_path),
            {
                "functions": [
                    fn.to_json(template={}, source_location=loc) for fn in functions_payload
                ]
            },
        )

        subprocess.run(
            [
                "symtab2gb",
                "--goto-functions",
                str(functions_path),
                "--out",
                str(gb_path),
                str(symtab_path),
            ],
            check=True,
        )

        cmd = ["cbmc", "--function", function_def.name, "--trace"]
        if cbmc_args:
            cmd.extend(cbmc_args)
        cmd.append(str(gb_path))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if show_output:
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
        return result


def _normalize_body(body: Iterable, function_def: GotoFunctionDef) -> list:
    """Normalize a function body for CBMC.

    - Inserts missing `Decl` for any variables referenced in the body.
    - Appends `SetReturnValue(0)` if no return value is provided.
    - Appends `EndFunction()` if missing.

    This is useful for small builder programs where you don't want to
    hand‑write boilerplate or explicit control-flow layout. If you need
    precise block ordering or GOTO targets, pass `normalize=False`.
    """
    normalized = list(body)
    vars_in_body = _collect_vars(normalized)

    existing_decl = {
        instr.symbol.name
        for instr in normalized
        if isinstance(instr, Decl) and isinstance(instr.symbol, Var)
    }
    for var in vars_in_body:
        if var.name not in existing_decl:
            normalized.insert(0, Decl(symbol=var))

    if not any(isinstance(instr, SetReturnValue) for instr in normalized):
        normalized.append(SetReturnValue(value=Constant(0, function_def.return_type)))

    if not any(isinstance(instr, EndFunction) for instr in normalized):
        normalized.append(EndFunction())

    return normalized


def _collect_vars(instructions: Iterable) -> list[Var]:
    seen = {}
    for instr in instructions:
        if isinstance(instr, Assign):
            _collect_vars_from_expr(instr.lhs, seen)
            _collect_vars_from_expr(instr.rhs, seen)
        elif isinstance(instr, Assert):
            _collect_vars_from_expr(instr.guard, seen)
        elif isinstance(instr, SetReturnValue):
            _collect_vars_from_expr(instr.value, seen)
        elif isinstance(instr, Decl) and isinstance(instr.symbol, Var):
            seen[instr.symbol.name] = instr.symbol
    return list(seen.values())


def _collect_vars_from_expr(expr: Expr, seen: dict[str, Var]) -> None:
    from .ir import BinaryExpr, CompareExpr, Not, Typecast, Dereference, IndexExpr, AddressOf, SymbolExpr, Constant

    if isinstance(expr, Var):
        seen.setdefault(expr.name, expr)
    elif isinstance(expr, SymbolExpr):
        return
    elif isinstance(expr, Constant):
        return
    elif isinstance(expr, BinaryExpr):
        _collect_vars_from_expr(expr.lhs, seen)
        _collect_vars_from_expr(expr.rhs, seen)
    elif isinstance(expr, CompareExpr):
        _collect_vars_from_expr(expr.lhs, seen)
        _collect_vars_from_expr(expr.rhs, seen)
    elif isinstance(expr, Not):
        _collect_vars_from_expr(expr.value, seen)
    elif isinstance(expr, Typecast):
        _collect_vars_from_expr(expr.value, seen)
    elif isinstance(expr, Dereference):
        _collect_vars_from_expr(expr.value, seen)
    elif isinstance(expr, IndexExpr):
        _collect_vars_from_expr(expr.base, seen)
        _collect_vars_from_expr(expr.index, seen)
    elif isinstance(expr, AddressOf):
        _collect_vars_from_expr(expr.value, seen)


def _build_symtab(function_def: GotoFunctionDef, loc: SourceLocation) -> SymbolTableBuilder:
    from .ir import FunctionType

    builder = SymbolTableBuilder()
    fn_type = FunctionType(parameters=[], return_type=function_def.return_type)
    builder.add_function(function_def.name, fn_type, loc)
    builder.add_function("__CPROVER_initialize", FunctionType(parameters=[], return_type=EmptyType()), loc)

    for var in _collect_vars(function_def.body):
        identifier = f"{function_def.name}::{var.name}"
        builder.add_local(identifier, var.name, var.typ, loc)
    return builder


def _init_function_def() -> GotoFunctionDef:
    return GotoFunctionDef(
        name="__CPROVER_initialize",
        params=[],
        return_type=EmptyType(),
        body=[EndFunction()],
    )
