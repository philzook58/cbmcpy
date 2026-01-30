import sys
from pathlib import Path
import unittest
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from cbmc import parse_c_file  # noqa: E402


class TestExamplesRoundtrip(unittest.TestCase):
    def test_examples_roundtrip(self) -> None:
        if shutil.which("goto-cc") is None or shutil.which("goto-instrument") is None:
            self.skipTest("CBMC tools not available in PATH")

        example_files = [
            "arith.c",
            "assertions.c",
            "hello.c",
            "mymemcpy.c",
            "oob.c",
            "sumn.c",
            "swap.c",
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            for name in example_files:
                path = ROOT / "examples" / name
                symtab, functions = parse_c_file(str(path), output_dir=tmp_dir)
                self.assertTrue(symtab.symbols)
                self.assertTrue(functions.functions)


if __name__ == "__main__":
    unittest.main()
