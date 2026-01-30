import sys
from typing import Any, cast
from pathlib import Path
import unittest
import shutil
import tempfile
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from cbmc import (  # noqa: E402
    load_json,
    parse_goto_functions,
    parse_json_ui,
    parse_symbol_table,
    strip_json_ui,
    wrap_json_ui,
    parse_c_file,
    Signed,
    SignedBVType,
    SET_RETURN_VALUE,
    GotoFunctionDef,
    run_cbmc,
    SymbolExpr,
    Constant,
    Assign,
    Assert,
    Decl,
    EndFunction,
    SetReturnValue,
    SourceLocation,
    SymbolTableBuilder,
    FunctionType,
)
from cbmc import dump_json  # noqa: E402

OUTPUTS = ROOT / "outputs"


class TestRoundtrip(unittest.TestCase):
    def test_symbol_table_roundtrip(self) -> None:
        path = OUTPUTS / "assertions_symbol_table.json"
        data = load_json(str(path))
        symtab = parse_symbol_table(data)
        payload = symtab.to_payload()
        stripped = strip_json_ui(data, key="symbolTable")
        self.assertEqual(payload, stripped)

        wrapped = wrap_json_ui(payload, program="goto-instrument")
        parsed = parse_json_ui(wrapped)
        self.assertEqual(parsed.payload_by_key("symbolTable"), payload)

    def test_goto_functions_roundtrip(self) -> None:
        path = OUTPUTS / "assertions_goto_functions.json"
        data = load_json(str(path))
        functions = parse_goto_functions(data)
        payload = functions.to_payload()
        stripped = strip_json_ui(data, key="functions")
        self.assertEqual(payload, stripped)

        wrapped = wrap_json_ui(payload, program="goto-instrument")
        parsed = parse_json_ui(wrapped)
        self.assertEqual(parsed.payload_by_key("functions"), payload)

    def test_strip_json_ui_multi_payload(self) -> None:
        payload = {"symbolTable": {"x": {"name": "x"}}}
        wrapped = wrap_json_ui(payload, program="demo")
        self.assertEqual(strip_json_ui(wrapped), payload)
        self.assertEqual(strip_json_ui(payload), payload)

    def test_parse_c_file(self) -> None:
        if shutil.which("goto-cc") is None or shutil.which("goto-instrument") is None:
            self.skipTest("CBMC tools not available in PATH")

        with tempfile.TemporaryDirectory() as tmp_dir:
            c_file = ROOT / "examples" / "assertions.c"
            symtab, functions = parse_c_file(str(c_file), output_dir=tmp_dir)

            self.assertTrue(symtab.symbols)
            self.assertTrue(functions.functions)

    def test_generate_and_run_cbmc(self) -> None:
        if (
            shutil.which("goto-cc") is None
            or shutil.which("goto-instrument") is None
            or shutil.which("symtab2gb") is None
        ):
            self.skipTest("CBMC tools not available in PATH")

        a = Signed("a", 32)
        b = Signed("b", 32)
        fn = GotoFunctionDef(
            name="add",
            params=[a, b],
            return_type=SignedBVType(32),
            body=[SET_RETURN_VALUE(a + b)],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            gb_path = run_cbmc(fn, output_dir=tmp_dir)
            json_path = Path(tmp_dir) / "generated_goto.json"
            import subprocess

            with open(json_path, "w", encoding="utf-8") as handle:
                subprocess.run(
                    [
                        "goto-instrument",
                        "--show-goto-functions",
                        "--json-ui",
                        str(gb_path),
                    ],
                    check=True,
                    stdout=handle,
                )
            data = load_json(str(json_path))
            payload = strip_json_ui(data, key="functions")
            functions = payload["functions"]
            add_fn = next((f for f in functions if f.get("name") == "add"), None)
            if add_fn is None:
                self.fail("Expected function 'add' to be present in JSON")
            add_fn = cast(dict[str, Any], add_fn)
            instructions = add_fn.get("instructions", [])
            self.assertTrue(any(i.get("instructionId") == "SET_RETURN_VALUE" for i in instructions))

    def test_programmatic_assert_counterexample(self) -> None:
        if (
            shutil.which("goto-cc") is None
            or shutil.which("goto-instrument") is None
            or shutil.which("symtab2gb") is None
            or shutil.which("cbmc") is None
        ):
            self.skipTest("CBMC tools not available in PATH")

        with tempfile.TemporaryDirectory() as tmp_dir:
            loc = SourceLocation(file="<generated>", function="main", line="1")
            int32 = SignedBVType(32)
            main_type = FunctionType(parameters=[], return_type=int32)

            x_id = "main::x"
            y_id = "main::y"
            z_id = "main::z"
            x = SymbolExpr(x_id, int32)
            y = SymbolExpr(y_id, int32)
            z = SymbolExpr(z_id, int32)

            builder = SymbolTableBuilder()
            builder.add_function("main", main_type, loc)
            builder.add_local(x_id, "x", int32, loc)
            builder.add_local(y_id, "y", int32, loc)
            builder.add_local(z_id, "z", int32, loc)

            body = [
                Decl(symbol=x),
                Decl(symbol=y),
                Decl(symbol=z),
                Assign(lhs=z, rhs=x + y),
                Assert(guard=z > Constant(0, int32)),
                SetReturnValue(value=Constant(0, int32)),
                EndFunction(),
            ]

            main_fn = GotoFunctionDef(name="main", params=[], return_type=int32, body=body)
            functions_payload = {"functions": [main_fn.to_json(template={}, source_location=loc)]}

            symtab_path = Path(tmp_dir) / "symtab.json"
            functions_path = Path(tmp_dir) / "functions.json"
            dump_json(str(symtab_path), builder.to_payload())
            dump_json(str(functions_path), functions_payload)

            gb_path = Path(tmp_dir) / "patched.gb"
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

            result = subprocess.run(
                ["cbmc", "--function", "main", "--trace", str(gb_path)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            combined = (result.stdout + result.stderr).lower()
            self.assertTrue("failed" in combined or "failure" in combined or "violation" in combined)




if __name__ == "__main__":
    unittest.main()
