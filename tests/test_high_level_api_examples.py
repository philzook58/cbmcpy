# ruff: noqa: E402
import sys
from pathlib import Path
import unittest
import shutil

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from cbmc import (
    Signed,
    GotoProgram,
    Assign,
    Assert,
    verify,
    ArrayType,
    Constant,
    SignedBVType,
)  # noqa: E402


def _array_var():
    int32 = SignedBVType(32)
    index_type = SignedBVType(64)
    arr_type = ArrayType(int32, Constant(4, index_type))
    arr = Signed("a", 32)
    return type(arr)(name="a", typ=arr_type)


class TestHighLevelApiExamples(unittest.TestCase):
    def test_passing_and_failing_programs(self) -> None:
        if shutil.which("symtab2gb") is None or shutil.which("cbmc") is None:
            self.skipTest("CBMC tools not available in PATH")

        x = Signed("x", 64)
        y = Signed("y", 64)
        a = _array_var()

        passing = [
            ("x_not_zero", GotoProgram([Assign(x, 1), Assert(x != 0)])),
            (
                "sum_positive",
                GotoProgram([Assign(x, 1), Assign(y, 1), Assert(x + y > 0)]),
            ),
            (
                "bool_ops",
                GotoProgram(
                    [
                        Assign(x, 1),
                        Assign(y, 2),
                        Assert((x < y) & (y > 0)),
                        Assert((x < 0) | (y > 0)),
                        Assert((x == 1) ^ (y == 1)),
                        Assign(x, -x),
                        Assert(x == -1),
                    ]
                ),
            ),
        ]

        failing = [
            ("x_zero", GotoProgram([Assign(x, 0), Assert(x != 0)])),
            (
                "sum_nonpositive",
                GotoProgram([Assign(x, -1), Assign(y, 0), Assert(x + y > 0)]),
            ),
            (
                "array_oob",
                GotoProgram(
                    [
                        Assign(a[0], Constant(0, SignedBVType(32))),
                        Assign(a[4], Constant(1, SignedBVType(32))),
                    ]
                ),
            ),
        ]

        for name, program in passing:
            with self.subTest(name=name):
                result = verify(program, show_output=False)
                self.assertEqual(result.returncode, 0)

        for name, program in failing:
            with self.subTest(name=name):
                result = verify(program, show_output=False)
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
