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
    Assign,
    Assert,
    verify,
    Decl,
    Goto,
    Not,
    EndFunction,
    SetReturnValue,
    ArrayType,
    IndexExpr,
    SignedBVType,
    FunctionType,
    FunctionSymbol,
    FunctionCall,
    PointerType,
    AddressOf,
    SymbolTableBuilder,
    SourceLocation,
    SymbolEntry,
    GotoFunctionDef,
    Dereference,
)


class TestExamplesBuilderIr(unittest.TestCase):
    def test_examples_builder_ir(self) -> None:
        if shutil.which("symtab2gb") is None or shutil.which("cbmc") is None:
            self.skipTest("CBMC tools not available in PATH")

        self._arith_example()
        self._assertions_example()
        self._sumn_example()
        # self._hello_example()
        self._mymemcpy_example()
        self._swap_example()

    def _arith_example(self) -> None:
        x = Signed("x", 32)
        prog = GotoProgram([Assign(x, 1 + 2), Assert(x == 3)])
        result = verify(prog, show_output=False)
        self.assertEqual(result.returncode, 0)

    def _assertions_example(self) -> None:
        int32 = SignedBVType(32)
        index_type = SignedBVType(64)
        arr_type = ArrayType(int32, Constant(4, index_type))
        a = Signed("a", 32)
        a = type(a)(name="a", typ=arr_type)

        body = [
            Decl(symbol=a),
            Assign(a[0], Constant(0, int32)),
            Assign(a[1], Constant(1, int32)),
            Assign(a[2], Constant(2, int32)),
            Assign(a[3], Constant(3, int32)),
            Assert(a[3] != Constant(3, int32)),
        ]
        prog = GotoProgram(body)
        result = verify(prog, show_output=False)
        self.assertNotEqual(result.returncode, 0)

    def _sumn_example(self) -> None:
        i = Signed("i", 32)
        n = Signed("n", 32)
        total = Signed("sum", 32)
        int32 = i.typ

        body = [
            Decl(symbol=total, location_number=1),
            Decl(symbol=i, location_number=2),
            Decl(symbol=n, location_number=3),
            Assign(n, Constant(4, int32)),
            Assign(total, Constant(0, int32)),
            Assign(i, Constant(1, int32)),
            Goto(guard=Not(i <= n), targets=[11], location_number=7),
            Assign(total, total + i),
            Assign(i, i + Constant(1, int32)),
            Goto(
                guard=(Constant(0, int32) != Constant(1, int32)),
                targets=[7],
                location_number=10,
            ),
            Assert(Not(total != Constant(10, int32))),
            SetReturnValue(value=Constant(0, int32), location_number=12),
            EndFunction(location_number=13),
        ]
        prog = GotoProgram(body)
        result = verify(prog, show_output=False, normalize=False)
        self.assertEqual(result.returncode, 0)

    """
    def _hello_example(self) -> None:
        self.skipTest("stdio/printf requires extra system symbols not yet modeled in builder symtab")
        char = SignedBVType(8)
        char_ptr = PointerType(char)
        size = Constant(15, SignedBVType(64))
        string_type = ArrayType(char, size)
        string = StringConstant("Hello, World!\n", string_type)
        index0 = IndexExpr(string, Constant(0, SignedBVType(64)), char)
        arg = AddressOf(index0, char_ptr)
        printf_type = FunctionType(parameters=[char_ptr], return_type=SignedBVType(32), ellipsis=True)
        printf = FunctionSymbol("printf", printf_type)

        body = [
            FunctionCall(function=printf, args=[arg], lhs=None),
            SetReturnValue(value=Constant(0, SignedBVType(32))),
            EndFunction(),
        ]
        prog = GotoProgram(body)

        loc = SourceLocation(file="<generated>", function="main", line="1")
        symtab = SymbolTableBuilder()
        symtab.add_function("main", FunctionType(parameters=[], return_type=SignedBVType(32)), loc)
        symtab.add_function(
            "printf",
            printf_type,
            loc,
            is_extern=True,
            is_lvalue=True,
        )

        result = verify(prog, show_output=False, symtab_builder=symtab)
        self.assertEqual(result.returncode, 0)
    """

    def _mymemcpy_example(self) -> None:
        int32 = SignedBVType(32)
        index_type = SignedBVType(64)
        byte = SignedBVType(8)
        arr_type = ArrayType(byte, Constant(4, index_type))
        src = type(Signed("src", 8))(name="src", typ=arr_type)
        dest = type(Signed("dest", 8))(name="dest", typ=arr_type)
        i = Signed("i", 32)

        body = [
            Decl(symbol=src, location_number=1),
            Decl(symbol=dest, location_number=2),
            Decl(symbol=i, location_number=3),
            Assign(src[0], Constant(1, byte)),
            Assign(src[1], Constant(2, byte)),
            Assign(src[2], Constant(3, byte)),
            Assign(src[3], Constant(4, byte)),
            Assign(i, Constant(0, int32)),
            Goto(guard=Not(i < Constant(4, int32)), targets=[13], location_number=9),
            Assign(IndexExpr(dest, i, byte), IndexExpr(src, i, byte)),
            Assign(i, i + Constant(1, int32)),
            Goto(
                guard=(Constant(0, int32) != Constant(1, int32)),
                targets=[9],
                location_number=12,
            ),
            Assert(IndexExpr(dest, Constant(3, index_type), byte) != Constant(4, byte)),
            SetReturnValue(value=Constant(0, int32)),
            EndFunction(),
        ]

        prog = GotoProgram(body)
        result = verify(prog, show_output=False, normalize=False)
        self.assertNotEqual(result.returncode, 0)

    def _swap_example(self) -> None:
        int32 = SignedBVType(32)
        int_ptr = PointerType(int32)

        src_param = type(Signed("src", 32))(name="src", typ=int_ptr)
        dst_param = type(Signed("dst", 32))(name="dst", typ=int_ptr)
        tmp = Signed("tmp", 32)

        swap_body = [
            Decl(symbol=tmp),
            Assign(tmp, Dereference(src_param, int32)),
            Assign(Dereference(src_param, int32), Dereference(dst_param, int32)),
            Assign(Dereference(dst_param, int32), tmp),
            SetReturnValue(value=Constant(0, int32)),
            EndFunction(),
        ]
        swap_def = GotoFunctionDef(
            name="swap",
            params=[src_param, dst_param],
            return_type=int32,
            body=swap_body,
        )

        x = Signed("x", 32)
        y = Signed("y", 32)
        swap_type = FunctionType(parameters=[int_ptr, int_ptr], return_type=int32)
        swap_sym = FunctionSymbol("swap", swap_type)

        main_body = [
            Decl(symbol=x),
            Decl(symbol=y),
            Assign(x, Constant(1, int32)),
            Assign(y, Constant(2, int32)),
            FunctionCall(function=swap_sym, args=[AddressOf(x, int_ptr), AddressOf(x, int_ptr)], lhs=None),
            Assert(x == Constant(2, int32)),
            SetReturnValue(value=Constant(0, int32)),
            EndFunction(),
        ]
        main_def = GotoFunctionDef(
            name="main",
            params=[],
            return_type=int32,
            body=main_body,
        )

        loc = SourceLocation(file="<generated>", function="main", line="1")
        symtab = SymbolTableBuilder()
        symtab.add_function("main", FunctionType(parameters=[], return_type=int32), loc)
        symtab.add_function("swap", swap_type, loc)
        symtab.add_local("main::x", "x", int32, loc)
        symtab.add_local("main::y", "y", int32, loc)
        symtab.add(SymbolEntry(name="swap::src", base_name="src", typ=int_ptr, location=loc, is_parameter=True))
        symtab.add(SymbolEntry(name="swap::dst", base_name="dst", typ=int_ptr, location=loc, is_parameter=True))
        symtab.add_local("swap::tmp", "tmp", int32, loc)

        result = verify(
            main_def,
            show_output=False,
            normalize=False,
            symtab_builder=symtab,
            extra_functions=[swap_def],
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
