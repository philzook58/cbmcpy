from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


class Type:
    def to_json(self) -> dict[str, Any]:
        raise NotImplementedError

    def to_c(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class SignedBVType(Type):
    width: int

    def to_json(self) -> dict[str, Any]:
        return {
            "id": "signedbv",
            "namedSub": {"width": {"id": str(self.width)}},
        }

    def to_c(self) -> str:
        if self.width == 8:
            return "signed char"
        if self.width == 16:
            return "short"
        if self.width == 32:
            return "int"
        if self.width == 64:
            return "long long"
        raise ValueError(f"Unsupported signed width: {self.width}")


@dataclass(frozen=True)
class BoolType(Type):
    def to_json(self) -> dict[str, Any]:
        return {"id": "bool"}

    def to_c(self) -> str:
        return "_Bool"


@dataclass(frozen=True)
class EmptyType(Type):
    def to_json(self) -> dict[str, Any]:
        return {"id": "empty"}

    def to_c(self) -> str:
        return "void"


@dataclass(frozen=True)
class FunctionType(Type):
    parameters: list[Type]
    return_type: Type
    ellipsis: bool = False

    def to_json(self) -> dict[str, Any]:
        params = [
            {"id": "parameter", "namedSub": {"type": param.to_json()}}
            for param in self.parameters
        ]
        named_sub = {}
        if self.ellipsis:
            named_sub["ellipsis"] = {"id": "1"}
        return {
            "id": "code",
            "namedSub": {
                "parameters": {"id": "", "namedSub": named_sub, "sub": params},
                "return_type": self.return_type.to_json(),
            },
        }

    def to_c(self) -> str:
        return "void"


@dataclass(frozen=True)
class Expr:
    def to_json(self, *, function_name: str) -> dict[str, Any]:
        raise NotImplementedError

    def __add__(self, other: "Expr") -> "Expr":
        return BinaryExpr(op="+", lhs=self, rhs=other)

    def __lt__(self, other: "Expr | int | bool") -> "Expr":
        return CompareExpr(op="<", lhs=self, rhs=_coerce_other(other, self))

    def __le__(self, other: "Expr | int | bool") -> "Expr":
        return CompareExpr(op="<=", lhs=self, rhs=_coerce_other(other, self))

    def __gt__(self, other: "Expr | int | bool") -> "Expr":
        return CompareExpr(op=">", lhs=self, rhs=_coerce_other(other, self))

    def __ge__(self, other: "Expr | int | bool") -> "Expr":
        return CompareExpr(op=">=", lhs=self, rhs=_coerce_other(other, self))

    def __eq__(self, other: object) -> "Expr":  # type: ignore[override]
        if isinstance(other, Expr):
            rhs = other
        elif isinstance(other, (int, bool)):
            rhs = _coerce_other(other, self)
        else:
            return NotImplemented
        return CompareExpr(op="=", lhs=self, rhs=rhs)

    def __ne__(self, other: object) -> "Expr":  # type: ignore[override]
        if isinstance(other, Expr):
            rhs = other
        elif isinstance(other, (int, bool)):
            rhs = _coerce_other(other, self)
        else:
            return NotImplemented
        return CompareExpr(op="notequal", lhs=self, rhs=rhs)

    def __invert__(self) -> "Expr":
        return Not(value=self)

    def __getitem__(self, index: "Expr | int") -> "Expr":
        return _index_expr(self, index)

    def __and__(self, other: "Expr | int | bool") -> "Expr":
        rhs = _coerce_other(other, self)
        if _is_bool_expr(self) and _is_bool_expr(rhs):
            return LogicalExpr(op="and", lhs=self, rhs=rhs)
        return BinaryExpr(op="bitand", lhs=self, rhs=rhs)

    def __or__(self, other: "Expr | int | bool") -> "Expr":
        rhs = _coerce_other(other, self)
        if _is_bool_expr(self) and _is_bool_expr(rhs):
            return LogicalExpr(op="or", lhs=self, rhs=rhs)
        return BinaryExpr(op="bitor", lhs=self, rhs=rhs)

    def __xor__(self, other: "Expr | int | bool") -> "Expr":
        rhs = _coerce_other(other, self)
        if _is_bool_expr(self) and _is_bool_expr(rhs):
            return CompareExpr(op="notequal", lhs=self, rhs=rhs)
        return BinaryExpr(op="bitxor", lhs=self, rhs=rhs)

    def __neg__(self) -> "Expr":
        return UnaryExpr(op="unary-", value=self)


@dataclass(frozen=True, eq=False)
class Var(Expr):
    name: str
    typ: Type

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "symbol",
            "namedSub": {
                "identifier": {"id": f"{function_name}::{self.name}"},
                "type": self.typ.to_json(),
            },
        }


@dataclass(frozen=True, eq=False)
class SymbolExpr(Expr):
    identifier: str
    typ: Type

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "symbol",
            "namedSub": {
                "identifier": {"id": self.identifier},
                "type": self.typ.to_json(),
            },
        }


@dataclass(frozen=True, eq=False)
class Constant(Expr):
    value: str | int
    typ: Type
    base: str | None = None

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        value_id: str
        if isinstance(self.value, int) and isinstance(self.typ, SignedBVType):
            value_id = _encode_bitvector_value(self.value, self.typ.width)
        else:
            value_id = str(self.value)
        named_sub = {
            "type": self.typ.to_json(),
            "value": {"id": value_id},
        }
        if self.base is not None:
            named_sub["#base"] = {"id": self.base}
        return {
            "id": "constant",
            "namedSub": named_sub,
        }


@dataclass(frozen=True, eq=False)
class Nil(Expr):
    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {"id": "nil"}


@dataclass(frozen=True, eq=False)
class Typecast(Expr):
    value: Expr
    target_type: Type

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "typecast",
            "namedSub": {"type": self.target_type.to_json()},
            "sub": [self.value.to_json(function_name=function_name)],
        }


@dataclass(frozen=True, eq=False)
class FunctionSymbol(Expr):
    name: str
    signature: FunctionType

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "symbol",
            "namedSub": {
                "identifier": {"id": self.name},
                "type": self.signature.to_json(),
            },
        }


@dataclass(frozen=True, eq=False)
class BinaryExpr(Expr):
    op: str
    lhs: Expr
    rhs: Expr

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        lhs_json = self.lhs.to_json(function_name=function_name)
        rhs_json = self.rhs.to_json(function_name=function_name)
        typ = _expr_type(self.lhs, self.rhs)
        return {
            "id": self.op,
            "namedSub": {"type": typ.to_json()},
            "sub": [lhs_json, rhs_json],
        }


@dataclass(frozen=True, eq=False)
class LogicalExpr(Expr):
    op: str
    lhs: Expr
    rhs: Expr

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": self.op,
            "namedSub": {"type": BoolType().to_json()},
            "sub": [
                self.lhs.to_json(function_name=function_name),
                self.rhs.to_json(function_name=function_name),
            ],
        }


@dataclass(frozen=True, eq=False)
class UnaryExpr(Expr):
    op: str
    value: Expr

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        typ = _find_var_type(self.value)
        if typ is None:
            raise ValueError("Unable to infer unary expression type")
        return {
            "id": self.op,
            "namedSub": {"type": typ.to_json()},
            "sub": [self.value.to_json(function_name=function_name)],
        }


@dataclass(frozen=True, eq=False)
class CompareExpr(Expr):
    op: str
    lhs: Expr
    rhs: Expr

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": self.op,
            "namedSub": {"type": BoolType().to_json()},
            "sub": [
                self.lhs.to_json(function_name=function_name),
                self.rhs.to_json(function_name=function_name),
            ],
        }


@dataclass(frozen=True, eq=False)
class Not(Expr):
    value: Expr

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "not",
            "namedSub": {"type": BoolType().to_json()},
            "sub": [self.value.to_json(function_name=function_name)],
        }


@dataclass(frozen=True)
class PointerType(Type):
    element: Type
    width: int = 64

    def to_json(self) -> dict[str, Any]:
        return {
            "id": "pointer",
            "namedSub": {"width": {"id": str(self.width)}},
            "sub": [self.element.to_json()],
        }

    def to_c(self) -> str:
        return f"{self.element.to_c()} *"


@dataclass(frozen=True)
class ArrayType(Type):
    element: Type
    size: Expr

    def to_json(self) -> dict[str, Any]:
        return {
            "id": "array",
            "namedSub": {"size": self.size.to_json(function_name="")},
            "sub": [self.element.to_json()],
        }

    def to_c(self) -> str:
        return f"{self.element.to_c()}[]"


@dataclass(frozen=True, eq=False)
class StringConstant(Expr):
    value: str
    array_type: ArrayType

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "string_constant",
            "namedSub": {
                "type": self.array_type.to_json(),
                "value": {"id": self.value},
            },
        }


@dataclass(frozen=True, eq=False)
class IndexExpr(Expr):
    base: Expr
    index: Expr
    typ: Type

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "index",
            "namedSub": {"type": self.typ.to_json()},
            "sub": [
                self.base.to_json(function_name=function_name),
                self.index.to_json(function_name=function_name),
            ],
        }


@dataclass(frozen=True, eq=False)
class AddressOf(Expr):
    value: Expr
    typ: Type

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "address_of",
            "namedSub": {"type": self.typ.to_json()},
            "sub": [self.value.to_json(function_name=function_name)],
        }


@dataclass(frozen=True, eq=False)
class Dereference(Expr):
    value: Expr
    typ: Type

    def to_json(self, *, function_name: str) -> dict[str, Any]:
        return {
            "id": "dereference",
            "namedSub": {"type": self.typ.to_json()},
            "sub": [self.value.to_json(function_name=function_name)],
        }


@dataclass(frozen=True)
class SourceLocation:
    file: str
    function: str
    line: str
    working_directory: str | None = None

    def to_json(self) -> dict[str, Any]:
        data = {
            "file": self.file,
            "function": self.function,
            "line": self.line,
        }
        if self.working_directory is not None:
            data["workingDirectory"] = self.working_directory
        return data


@dataclass(frozen=True, kw_only=True)
class Instruction:
    labels: list[str] = field(default_factory=list)
    location_number: int | None = None

    def to_json(
        self,
        *,
        function_name: str,
        location_number: int,
        source_location: SourceLocation,
    ) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class SetReturnValue(Instruction):
    value: Expr

    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        code = _code_statement(
            "return",
            [self.value.to_json(function_name=function_name)],
        )
        return _instruction_base(
            "SET_RETURN_VALUE",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            code=code,
        )


@dataclass(frozen=True)
class Assign(Instruction):
    lhs: Expr
    rhs: Expr | int | bool

    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        rhs = self.rhs if isinstance(self.rhs, Expr) else _coerce_other(self.rhs, self.lhs)
        code = _code_statement(
            "assign",
            [
                self.lhs.to_json(function_name=function_name),
                rhs.to_json(function_name=function_name),
            ],
        )
        return _instruction_base(
            "ASSIGN",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            code=code,
        )


@dataclass(frozen=True)
class Decl(Instruction):
    symbol: Expr

    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        code = _code_statement(
            "decl",
            [self.symbol.to_json(function_name=function_name)],
        )
        return _instruction_base(
            "DECL",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            code=code,
        )


@dataclass(frozen=True)
class Dead(Instruction):
    symbol: Expr

    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        code = _code_statement(
            "dead",
            [self.symbol.to_json(function_name=function_name)],
        )
        return _instruction_base(
            "DEAD",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            code=code,
        )


@dataclass(frozen=True)
class FunctionCall(Instruction):
    function: Expr
    args: list[Expr]
    lhs: Expr | None = None

    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        lhs_expr = self.lhs if self.lhs is not None else Nil()
        code = _code_statement(
            "function_call",
            [
                lhs_expr.to_json(function_name=function_name),
                self.function.to_json(function_name=function_name),
                {"id": "arguments", "sub": [arg.to_json(function_name=function_name) for arg in self.args]},
            ],
        )
        return _instruction_base(
            "FUNCTION_CALL",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            code=code,
        )


@dataclass(frozen=True)
class Other(Instruction):
    code: dict[str, Any]

    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "OTHER",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            code=self.code,
        )


@dataclass(frozen=True)
class GuardedInstruction(Instruction):
    guard: dict[str, Any] | Expr

    def guard_json(self, function_name: str) -> dict[str, Any]:
        if isinstance(self.guard, Expr):
            return self.guard.to_json(function_name=function_name)
        return self.guard


@dataclass(frozen=True)
class Goto(GuardedInstruction):
    targets: list[int] = field(default_factory=list)

    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "GOTO",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            guard=self.guard_json(function_name),
            targets=self.targets,
        )


@dataclass(frozen=True)
class Assume(GuardedInstruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "ASSUME",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            guard=self.guard_json(function_name),
        )


@dataclass(frozen=True)
class Assert(GuardedInstruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "ASSERT",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
            guard=self.guard_json(function_name),
        )


@dataclass(frozen=True)
class Skip(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "SKIP",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class StartThread(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "START_THREAD",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class EndThread(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "END_THREAD",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class Location(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "LOCATION",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class EndFunction(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "END_FUNCTION",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class AtomicBegin(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "ATOMIC_BEGIN",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class AtomicEnd(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "ATOMIC_END",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class Throw(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "THROW",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class Catch(Instruction):
    def to_json(self, *, function_name: str, location_number: int, source_location: SourceLocation) -> dict[str, Any]:
        return _instruction_base(
            "CATCH",
            location_number=location_number,
            source_location=source_location,
            labels=self.labels,
        )


@dataclass(frozen=True)
class GotoFunctionDef:
    name: str
    params: list[Var]
    return_type: Type
    body: list[Instruction]

    def parameter_identifiers(self) -> list[str]:
        return [f"{self.name}::{param.name}" for param in self.params]

    def to_json(self, *, template: dict[str, Any], source_location: SourceLocation) -> dict[str, Any]:
        instructions = []
        for index, instr in enumerate(self.body, start=1):
            loc_number = instr.location_number or index
            instructions.append(
                instr.to_json(
                    function_name=self.name,
                    location_number=loc_number,
                    source_location=source_location,
                )
            )
        return {
            "name": self.name,
            "instructions": instructions,
            "isBodyAvailable": True,
            "isHidden": template.get("isHidden", False),
            "isInternal": template.get("isInternal", False),
            "parameterIdentifiers": self.parameter_identifiers(),
        }


def Signed(name: str, width: int) -> Var:
    return Var(name=name, typ=SignedBVType(width))


def Bool(name: str) -> Var:
    return Var(name=name, typ=BoolType())


def Ptr(name: str, element: Type, *, width: int = 64) -> Var:
    return Var(name=name, typ=PointerType(element, width=width))


def Array(name: str, element: Type, size: Expr | int, *, index_width: int = 64) -> Var:
    size_expr = size
    if isinstance(size, int):
        size_expr = Constant(size, SignedBVType(index_width))
    return Var(name=name, typ=ArrayType(element, size_expr))  # type: ignore[arg-type]


def SET_RETURN_VALUE(expr: Expr) -> SetReturnValue:
    return SetReturnValue(value=expr)


def _expr_type(lhs: Expr, rhs: Expr) -> Type:
    lhs_type = _find_var_type(lhs)
    rhs_type = _find_var_type(rhs)
    if lhs_type is not None and rhs_type is not None:
        if type(lhs_type) is type(rhs_type) and lhs_type == rhs_type:
            return lhs_type
        if isinstance(lhs_type, PointerType) and isinstance(rhs_type, SignedBVType):
            return lhs_type
        if isinstance(rhs_type, PointerType) and isinstance(lhs_type, SignedBVType):
            return rhs_type
    if lhs_type is not None:
        return lhs_type
    if rhs_type is not None:
        return rhs_type
    raise ValueError("Unable to infer expression type")


def _find_var_type(expr: Expr) -> Type | None:
    if isinstance(expr, Var):
        return expr.typ
    if isinstance(expr, SymbolExpr):
        return expr.typ
    if isinstance(expr, Constant):
        return expr.typ
    if isinstance(expr, Typecast):
        return expr.target_type
    if isinstance(expr, IndexExpr):
        return expr.typ
    if isinstance(expr, Dereference):
        return expr.typ
    if isinstance(expr, BinaryExpr):
        return _find_var_type(expr.lhs) or _find_var_type(expr.rhs)
    if isinstance(expr, CompareExpr):
        return BoolType()
    if isinstance(expr, Not):
        return BoolType()
    return None


def _is_bool_expr(expr: Expr) -> bool:
    typ = _find_var_type(expr)
    return isinstance(typ, BoolType)


def _index_expr(base: Expr, index: Expr | int) -> Expr:
    base_type = _find_var_type(base)
    if not isinstance(base_type, ArrayType):
        raise ValueError("Indexing requires an array-typed expression")
    if isinstance(index, int):
        index_expr = Constant(index, SignedBVType(64))
    else:
        index_expr = index
    return IndexExpr(base, index_expr, base_type.element)


def _coerce_other(other: Expr | int | bool, reference: Expr) -> Expr:
    if isinstance(other, Expr):
        return other
    ref_type = _find_var_type(reference)
    if isinstance(other, bool):
        return Constant("true" if other else "false", BoolType())
    if isinstance(ref_type, Type):
        return Constant(other, ref_type)  # type: ignore[arg-type]
    return Constant(other, SignedBVType(32))


def _encode_bitvector_value(value: int, width: int) -> str:
    if width <= 0:
        raise ValueError("Bitvector width must be positive")
    modulo = 1 << width
    if value < 0:
        value = (modulo + value) % modulo
    hex_value = format(value, "X")
    if hex_value == "0":
        return "0"
    return hex_value.lstrip("0")


def _instruction_base(
    instruction_id: str,
    *,
    location_number: int,
    source_location: SourceLocation,
    labels: Iterable[str],
    code: dict[str, Any] | None = None,
    guard: dict[str, Any] | None = None,
    targets: list[int] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "instructionId": instruction_id,
        "locationNumber": location_number,
        "sourceLocation": source_location.to_json(),
    }
    if labels:
        data["labels"] = list(labels)
    if code is not None:
        data["code"] = code
    if guard is not None:
        data["guard"] = guard
    if targets is not None:
        data["targets"] = targets
    return data


def _code_statement(statement_id: str, sub: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": "code",
        "namedSub": {
            "statement": {"id": statement_id},
            "type": {"id": "empty"},
        },
        "sub": sub,
    }
