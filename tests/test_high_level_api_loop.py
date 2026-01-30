import sys
from pathlib import Path
import unittest
import shutil

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from cbmc import (  # noqa: E402
    Signed,
    Constant,
    GotoProgram,
    assign,
    assert_,
    verify,
    Decl,
    Goto,
    Not,
    EndFunction,
    SetReturnValue,
)


class TestHighLevelApiLoop(unittest.TestCase):
    def test_for_loop_sum(self) -> None:
        if shutil.which("symtab2gb") is None or shutil.which("cbmc") is None:
            self.skipTest("CBMC tools not available in PATH")

        i = Signed("i", 32)
        n = Signed("n", 32)
        total = Signed("sum", 32)

        int32 = i.typ
        one = Constant(1, int32)
        four = Constant(4, int32)
        ten = Constant(10, int32)

        # location numbers must match GOTO targets
        body = [
            Decl(symbol=total, location_number=1),
            Decl(symbol=i, location_number=2),
            Decl(symbol=n, location_number=3),
            assign(n, four),
            assign(total, Constant(0, int32)),
            assign(i, one),
            # if !(i <= n) goto end
            Goto(guard=Not(i <= n), targets=[11], location_number=7),
            assign(total, total + i),
            assign(i, i + one),
            # unconditional goto loop check
            Goto(guard=(Constant(0, int32) != Constant(1, int32)), targets=[7], location_number=10),
            assert_(Not(total != ten)),
            SetReturnValue(value=Constant(0, int32), location_number=12),
            EndFunction(location_number=13),
        ]

        prog = GotoProgram(body)
        result = verify(prog, show_output=False, normalize=False)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
