import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from cbmc import (  # noqa: E402
    Assert,
    Assign,
    AtomicBegin,
    AtomicEnd,
    BoolType,
    Catch,
    Constant,
    Decl,
    Dead,
    EndFunction,
    EndThread,
    FunctionCall,
    FunctionSymbol,
    FunctionType,
    Goto,
    Location,
    Other,
    Signed,
    SignedBVType,
    Skip,
    SourceLocation,
    StartThread,
    SET_RETURN_VALUE,
    SetReturnValue,
    Assume,
    Throw,
)


class TestInstructionTypes(unittest.TestCase):
    def setUp(self) -> None:
        self.loc = SourceLocation(file="test.c", function="f", line="1")
        self.function_name = "f"

    def _check_keys(self, data, instruction_id, expect_guard=False, expect_code=False, expect_targets=False):
        self.assertEqual(data.get("instructionId"), instruction_id)
        self.assertIn("locationNumber", data)
        self.assertIn("sourceLocation", data)
        if expect_guard:
            self.assertIn("guard", data)
        if expect_code:
            self.assertIn("code", data)
        if expect_targets:
            self.assertIn("targets", data)

    def test_instruction_serialization(self) -> None:
        a = Signed("a", 32)
        b = Signed("b", 32)
        guard = Constant(1, BoolType())
        func_sig = FunctionType(parameters=[SignedBVType(32), SignedBVType(32)], return_type=SignedBVType(32))
        func_sym = FunctionSymbol("add", func_sig)

        instructions = [
            Goto(guard=guard, targets=[3]),
            Assume(guard=guard),
            Assert(guard=guard),
            Other(code={"id": "code", "namedSub": {"statement": {"id": "skip"}, "type": {"id": "empty"}}, "sub": []}),
            Skip(),
            StartThread(),
            EndThread(),
            Location(),
            EndFunction(),
            AtomicBegin(),
            AtomicEnd(),
            SET_RETURN_VALUE(a + b),
            Assign(lhs=a, rhs=b),
            Decl(symbol=a),
            Dead(symbol=a),
            FunctionCall(function=func_sym, args=[Constant(1, SignedBVType(32)), Constant(2, SignedBVType(32))], lhs=a),
            Throw(),
            Catch(),
        ]

        for index, instr in enumerate(instructions, start=1):
            data = instr.to_json(
                function_name=self.function_name,
                location_number=index,
                source_location=self.loc,
            )
            if isinstance(instr, Goto):
                self._check_keys(data, "GOTO", expect_guard=True, expect_targets=True)
            elif isinstance(instr, Assume):
                self._check_keys(data, "ASSUME", expect_guard=True)
            elif isinstance(instr, Assert):
                self._check_keys(data, "ASSERT", expect_guard=True)
            elif isinstance(instr, Other):
                self._check_keys(data, "OTHER", expect_code=True)
            elif isinstance(instr, Skip):
                self._check_keys(data, "SKIP")
            elif isinstance(instr, StartThread):
                self._check_keys(data, "START_THREAD")
            elif isinstance(instr, EndThread):
                self._check_keys(data, "END_THREAD")
            elif isinstance(instr, Location):
                self._check_keys(data, "LOCATION")
            elif isinstance(instr, EndFunction):
                self._check_keys(data, "END_FUNCTION")
            elif isinstance(instr, AtomicBegin):
                self._check_keys(data, "ATOMIC_BEGIN")
            elif isinstance(instr, AtomicEnd):
                self._check_keys(data, "ATOMIC_END")
            elif isinstance(instr, SetReturnValue):
                self._check_keys(data, "SET_RETURN_VALUE", expect_code=True)
            elif isinstance(instr, Assign):
                self._check_keys(data, "ASSIGN", expect_code=True)
            elif isinstance(instr, Decl):
                self._check_keys(data, "DECL", expect_code=True)
            elif isinstance(instr, Dead):
                self._check_keys(data, "DEAD", expect_code=True)
            elif isinstance(instr, FunctionCall):
                self._check_keys(data, "FUNCTION_CALL", expect_code=True)
            elif isinstance(instr, Throw):
                self._check_keys(data, "THROW")
            elif isinstance(instr, Catch):
                self._check_keys(data, "CATCH")


if __name__ == "__main__":
    unittest.main()
