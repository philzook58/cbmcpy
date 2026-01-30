import sys
from pathlib import Path
import unittest
import shutil
import tempfile
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from cbmc import (  # noqa: E402
    AddressOf,
    ArrayType,
    Constant,
    Dereference,
    FunctionCall,
    FunctionSymbol,
    FunctionType,
    IndexExpr,
    Not,
    PointerType,
    SetReturnValue,
    SignedBVType,
    StringConstant,
    SymbolExpr,
    Typecast,
)
from cbmc import load_json, strip_json_ui, dump_json  # noqa: E402
from cbmc import parse_c_file  # noqa: E402


class TestExamplesIr(unittest.TestCase):
    def test_ir_matches_examples(self) -> None:
        if shutil.which("goto-cc") is None or shutil.which("goto-instrument") is None:
            self.skipTest("CBMC tools not available in PATH")

        with tempfile.TemporaryDirectory() as tmp_dir:
            def load_goto(example: str):
                path = ROOT / "examples" / example
                parse_c_file(str(path), output_dir=tmp_dir)
                goto_path = Path(tmp_dir) / f"{path.stem}_goto_functions.json"
                symtab_path = Path(tmp_dir) / f"{path.stem}_symbol_table.json"
                data = load_json(str(goto_path))
                symtab_data = load_json(str(symtab_path))
                payload = strip_json_ui(data, key="functions")
                symtab_payload = strip_json_ui(symtab_data, key="symbolTable")
                return payload["functions"], symtab_payload

            # arith.c: add returns a + b
            functions, symtab_payload = load_goto("arith.c")
            add_fn = next(fn for fn in functions if fn.get("name") == "add")
            ret_instr = next(
                ins for ins in add_fn.get("instructions", []) if ins.get("instructionId") == "SET_RETURN_VALUE"
            )
            a = SymbolExpr("add::a", SignedBVType(32))
            b = SymbolExpr("add::b", SignedBVType(32))
            ret = SetReturnValue(value=a + b)
            ret_json = ret.to_json(function_name="add", location_number=ret_instr["locationNumber"], source_location=_loc())
            self.assertEqual(ret_instr["code"], ret_json["code"])
            _roundtrip_with_patch(
                symtab_payload,
                functions,
                "arith_add",
                patch={"function": "add", "instructionId": "SET_RETURN_VALUE", "code": ret_json["code"]},
                output_dir=tmp_dir,
            )

            # sumn.c: loop guard uses !(i <= n)
            functions, symtab_payload = load_goto("sumn.c")
            sumn_fn = next(fn for fn in functions if fn.get("name") == "sumn")
            goto_instr = next(
                ins for ins in sumn_fn.get("instructions", []) if ins.get("instructionId") == "GOTO"
            )
            i = SymbolExpr("sumn::1::1::i", SignedBVType(32))
            n = SymbolExpr("sumn::n", SignedBVType(32))
            guard = Not(i <= n)
            guard_json = guard.to_json(function_name="sumn")
            self.assertEqual(goto_instr["guard"], guard_json)
            _roundtrip_with_patch(
                symtab_payload,
                functions,
                "sumn_guard",
                patch={"function": "sumn", "instructionId": "GOTO", "guard": guard_json},
                output_dir=tmp_dir,
            )

            # hello.c: printf("Hello, World!\n")
            functions, symtab_payload = load_goto("hello.c")
            main_fn = next(fn for fn in functions if fn.get("name") == "main")
            call_instr = next(
                ins
                for ins in main_fn.get("instructions", [])
                if ins.get("instructionId") == "FUNCTION_CALL"
                and ins.get("code", {}).get("sub", [None, {}])[1].get("namedSub", {}).get("identifier", {}).get("id")
                == "printf"
            )
            char = SignedBVType(8)
            char_ptr = PointerType(char, width=64)
            size = Constant("F", SignedBVType(64))
            array_type = ArrayType(char, size)
            string = StringConstant("Hello, World!\n", array_type)
            index = IndexExpr(string, Constant(0, SignedBVType(64)), char)
            arg = AddressOf(index, char_ptr)
            printf_type = FunctionType(parameters=[char_ptr], return_type=SignedBVType(32), ellipsis=True)
            printf = FunctionSymbol("printf", printf_type)
            call = FunctionCall(function=printf, args=[arg], lhs=None)
            call_json = call.to_json(function_name="main", location_number=call_instr["locationNumber"], source_location=_loc())
            self.assertEqual(call_instr["code"], call_json["code"])
            _roundtrip_with_patch(
                symtab_payload,
                functions,
                "hello_printf",
                patch={"function": "main", "instructionId": "FUNCTION_CALL", "code": call_json["code"]},
                output_dir=tmp_dir,
            )

            # mymemcpy.c: dest[i] = src[i]
            functions, symtab_payload = load_goto("mymemcpy.c")
            memcpy_fn = next(fn for fn in functions if fn.get("name") == "mymemcpy")
            assign_instr = next(
                ins
                for ins in memcpy_fn.get("instructions", [])
                if ins.get("instructionId") == "ASSIGN"
                and ins.get("code", {}).get("sub", [None])[0].get("id") == "dereference"
            )
            dest = SymbolExpr("mymemcpy::dest", char_ptr)
            src = SymbolExpr("mymemcpy::src", char_ptr)
            i = SymbolExpr("mymemcpy::1::1::i", SignedBVType(32))
            i64 = Typecast(i, SignedBVType(64))
            lhs_ptr = dest + i64
            rhs_ptr = src + i64
            lhs = Dereference(lhs_ptr, char)
            rhs = Dereference(rhs_ptr, char)
            assign_json = {
                "id": "code",
                "namedSub": {"statement": {"id": "assign"}, "type": {"id": "empty"}},
                "sub": [lhs.to_json(function_name="mymemcpy"), rhs.to_json(function_name="mymemcpy")],
            }
            self.assertEqual(assign_instr["code"], assign_json)
            _roundtrip_with_patch(
                symtab_payload,
                functions,
                "mymemcpy_assign",
                patch={"function": "mymemcpy", "instructionId": "ASSIGN", "code": assign_json},
                output_dir=tmp_dir,
            )


def _loc():
    from cbmc import SourceLocation

    return SourceLocation(file="<generated>", function="", line="1")


def _roundtrip_with_patch(symtab_payload, functions, tag, patch, output_dir):
    patched_functions = []
    for fn in functions:
        if fn.get("name") != patch["function"]:
            patched_functions.append(fn)
            continue
        updated_fn = dict(fn)
        updated_instructions = []
        replaced = False
        for ins in fn.get("instructions", []) or []:
            if ins.get("instructionId") != patch["instructionId"]:
                updated_instructions.append(ins)
                continue
            updated = dict(ins)
            if "code" in patch:
                updated["code"] = patch["code"]
            if "guard" in patch:
                updated["guard"] = patch["guard"]
            updated_instructions.append(updated)
            replaced = True
        if not replaced:
            raise AssertionError(f"Instruction {patch['instructionId']} not found in {patch['function']}")
        updated_fn["instructions"] = updated_instructions
        patched_functions.append(updated_fn)

    symtab_path = Path(output_dir) / f"{tag}_symtab.json"
    functions_path = Path(output_dir) / f"{tag}_functions.json"
    dump_json(str(symtab_path), symtab_payload)
    dump_json(str(functions_path), {"functions": patched_functions})

    out_gb = Path(output_dir) / f"{tag}.gb"
    subprocess.run(
        [
            "symtab2gb",
            "--goto-functions",
            str(functions_path),
            "--out",
            str(out_gb),
            str(symtab_path),
        ],
        check=True,
    )
    subprocess.run(
        ["goto-instrument", "--show-goto-functions", "--json-ui", str(out_gb)],
        check=True,
        stdout=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    unittest.main()
