import sys
from pathlib import Path
import unittest
import shutil

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from cbmc import Signed, GotoProgram, assign, assert_, verify  # noqa: E402


class TestHighLevelApi(unittest.TestCase):
    def test_verify_finds_counterexample(self) -> None:
        if (
            shutil.which("symtab2gb") is None
            or shutil.which("cbmc") is None
        ):
            self.skipTest("CBMC tools not available in PATH")

        x = Signed("x", 64)
        prog = GotoProgram([assign(x, 0), assert_(x != 0)])
        result = verify(prog, show_output=False)
        self.assertNotEqual(result.returncode, 0)
        combined = (result.stdout + result.stderr).lower()
        self.assertTrue("failed" in combined or "failure" in combined or "violation" in combined)


if __name__ == "__main__":
    unittest.main()
