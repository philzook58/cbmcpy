import sys
from pathlib import Path
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from cbmc import PyToGoto, translate_and_verify  # noqa: E402


class TestPythonTranslation(unittest.TestCase):
    def test_translate_success(self) -> None:
        program = "x = 1\nassert x == 1\n"
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_success_multiple_vars(self) -> None:
        program = "x = 1\ny = 2\nz = x + y\nassert z == 3\n"
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_success_not_and_compare(self) -> None:
        program = "x = 5\nassert not (x < 0)\n"
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_sumn_unrolled(self) -> None:
        program = (
            "sum = 0\n"
            "sum = sum + 1\n"
            "sum = sum + 2\n"
            "sum = sum + 3\n"
            "sum = sum + 4\n"
            "assert sum == 10\n"
        )
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_sumn_loop(self) -> None:
        program = (
            "sum = 0\n"
            "for i in range(1, 5):\n"
            "    sum = sum + i\n"
            "assert sum == 10\n"
        )
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_loop_step(self) -> None:
        program = (
            "sum = 0\n"
            "for i in range(1, 6, 2):\n"
            "    sum = sum + i\n"
            "assert sum == 9\n"
        )
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_while_loop(self) -> None:
        program = (
            "i = 0\n"
            "sum = 0\n"
            "while i < 4:\n"
            "    i = i + 1\n"
            "    sum = sum + i\n"
            "assert sum == 10\n"
        )
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_if_else(self) -> None:
        program = (
            "x = 0\n"
            "if x == 0:\n"
            "    y = 1\n"
            "else:\n"
            "    y = 2\n"
            "assert y == 1\n"
        )
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_if_no_else(self) -> None:
        program = (
            "x = 1\n"
            "if x > 0:\n"
            "    y = 3\n"
            "assert y == 3\n"
        )
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_array_setitem(self) -> None:
        program = (
            "a = [0, 0, 0, 0]\n"
            "x = 2\n"
            "a[1] = 1 + x\n"
            "assert a[1] == 3\n"
        )
        result = translate_and_verify(program, show_output=False)
        self.assertEqual(result.returncode, 0)

    def test_translate_failure(self) -> None:
        program = "x = 0\nassert x != 0\n"
        result = translate_and_verify(program, show_output=False)
        self.assertNotEqual(result.returncode, 0)

    def test_translate_failure_compare(self) -> None:
        program = "x = 1\nassert x > 10\n"
        result = translate_and_verify(program, show_output=False)
        self.assertNotEqual(result.returncode, 0)

    def test_translate_rejects_complex_assign(self) -> None:
        translator = PyToGoto()
        with self.assertRaises(ValueError):
            translator.translate("x, y = 1, 2")

    def test_translate_rejects_unsupported_expr(self) -> None:
        translator = PyToGoto()
        with self.assertRaises(ValueError):
            translator.translate("x = 1\nassert x * 2 == 2")

    def setUp(self) -> None:
        if shutil.which("symtab2gb") is None or shutil.which("cbmc") is None:
            self.skipTest("CBMC tools not available in PATH")


if __name__ == "__main__":
    unittest.main()
