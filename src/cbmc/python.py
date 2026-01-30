import ast
from dataclasses import dataclass
from typing import Dict, List

from .api import GotoFunction as GotoProgram, verify
from .ir import (
    Constant,
    ArrayType,
    Assign,
    Assert,
    Decl,
    EndFunction,
    Goto,
    Location,
    Not,
    SetReturnValue,
    Signed,
    SignedBVType,
    Var,
)


@dataclass
class TranslationResult:
    program: GotoProgram


class PyToGoto:
    def __init__(self) -> None:
        self.vars: Dict[str, Var] = {}
        self.body: List[object] = []
        self._pending_gotos: List[tuple[Goto, str]] = []
        self._label_counter = 0

    def translate(self, source: str) -> TranslationResult:
        tree = ast.parse(source)
        for stmt in tree.body:
            self._translate_stmt(stmt)
        body = self._finalize_body()
        program = GotoProgram(body)
        return TranslationResult(program=program)

    def _translate_stmt(self, stmt: ast.stmt) -> None:
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Subscript):
                    self._translate_subscript_assign(stmt.targets[0], stmt.value)
                    return
                raise ValueError("Only assignments to a single name or subscript are supported")
            name = stmt.targets[0].id
            if isinstance(stmt.value, ast.List):
                self._translate_array_init(name, stmt.value)
                return
            lhs = self._get_var(name)
            rhs = self._translate_expr(stmt.value)
            self.body.append(Assign(lhs=lhs, rhs=rhs))
            return
        if isinstance(stmt, ast.For):
            self._translate_for(stmt)
            return
        if isinstance(stmt, ast.While):
            self._translate_while(stmt)
            return
        if isinstance(stmt, ast.If):
            self._translate_if(stmt)
            return
        if isinstance(stmt, ast.Assert):
            guard = self._translate_expr(stmt.test)
            self.body.append(Assert(guard=guard))
            return
        raise ValueError(f"Unsupported statement: {type(stmt).__name__}")

    def _translate_expr(self, expr: ast.expr):
        if isinstance(expr, ast.Name):
            return self._get_var(expr.id)
        if isinstance(expr, ast.Subscript):
            return self._translate_subscript_expr(expr)
        if isinstance(expr, ast.Constant):
            if isinstance(expr.value, bool):
                return Constant(1 if expr.value else 0, Signed("_tmp", 1).typ)
            if isinstance(expr.value, int):
                return Constant(expr.value, Signed("_tmp", 32).typ)
            raise ValueError("Only int/bool constants supported")
        if isinstance(expr, ast.BinOp):
            left = self._translate_expr(expr.left)
            right = self._translate_expr(expr.right)
            if isinstance(expr.op, ast.Add):
                return left + right
            raise ValueError("Only + supported in binary ops")
        if isinstance(expr, ast.Compare):
            if len(expr.ops) != 1 or len(expr.comparators) != 1:
                raise ValueError("Only single comparisons supported")
            left = self._translate_expr(expr.left)
            right = self._translate_expr(expr.comparators[0])
            op = expr.ops[0]
            if isinstance(op, ast.NotEq):
                return left != right
            if isinstance(op, ast.Eq):
                return ~(left != right)
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
            raise ValueError("Unsupported comparison operator")
        if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
            inner = self._translate_expr(expr.operand)
            return ~inner
        raise ValueError(f"Unsupported expression: {type(expr).__name__}")

    def _get_var(self, name: str):
        if name not in self.vars:
            self.vars[name] = Signed(name, 32)
        return self.vars[name]

    def _get_array_var(self, name: str):
        if name not in self.vars:
            raise ValueError(f"Array '{name}' must be initialized before indexing")
        var = self.vars[name]
        if not isinstance(var.typ, ArrayType):
            raise ValueError(f"Variable '{name}' is not an array")
        return var

    def _translate_array_init(self, name: str, value: ast.List) -> None:
        if not all(isinstance(elt, ast.Constant) and isinstance(elt.value, int) for elt in value.elts):
            raise ValueError("Only int list literals are supported for array initialization")
        int32 = SignedBVType(32)
        size = Constant(len(value.elts), SignedBVType(64))
        arr_type = ArrayType(int32, size)
        arr = Signed(name, 32)
        arr = type(arr)(name=name, typ=arr_type)
        self.vars[name] = arr
        for idx, elt in enumerate(value.elts):
            if not isinstance(elt, ast.Constant) or not isinstance(elt.value, int):
                raise ValueError("Only int list literals are supported for array initialization")
            self.body.append(Assign(lhs=arr[idx], rhs=Constant(elt.value, int32)))

    def _translate_subscript_assign(self, target: ast.Subscript, value: ast.expr) -> None:
        if not isinstance(target.value, ast.Name):
            raise ValueError("Only name[index] assignments are supported")
        base = self._get_array_var(target.value.id)
        index_expr = self._translate_subscript_index(target.slice)
        rhs = self._translate_expr(value)
        self.body.append(Assign(lhs=base[index_expr], rhs=rhs))

    def _translate_subscript_expr(self, expr: ast.Subscript):
        if not isinstance(expr.value, ast.Name):
            raise ValueError("Only name[index] expressions are supported")
        base = self._get_array_var(expr.value.id)
        index_expr = self._translate_subscript_index(expr.slice)
        return base[index_expr]

    def _translate_subscript_index(self, index: ast.expr):
        if isinstance(index, ast.Slice):
            raise ValueError("Slice indexing is not supported")
        return self._translate_expr(index)

    def _finalize_body(self) -> List[object]:
        decls = [Decl(symbol=var) for var in self.vars.values()]
        return_value = SetReturnValue(value=Constant(0, SignedBVType(32)))
        end = EndFunction()
        body = decls + self.body + [return_value, end]
        return self._resolve_gotos(body)

    def _resolve_gotos(self, body: List[object]) -> List[object]:
        label_to_loc: Dict[str, int] = {}
        for index, instr in enumerate(body, start=1):
            if isinstance(instr, Location) and instr.labels:
                for label in instr.labels:
                    label_to_loc[label] = index
        if not self._pending_gotos:
            return body
        resolved: List[object] = []
        for instr in body:
            if isinstance(instr, Goto):
                pending = next((entry for entry in self._pending_gotos if entry[0] is instr), None)
                if pending is not None:
                    _, label = pending
                    if label not in label_to_loc:
                        raise ValueError(f"Unknown goto label: {label}")
                    instr = Goto(
                        guard=instr.guard,
                        targets=[label_to_loc[label]],
                        labels=instr.labels,
                        location_number=instr.location_number,
                    )
            resolved.append(instr)
        return resolved

    def _translate_for(self, stmt: ast.For) -> None:
        if not isinstance(stmt.target, ast.Name):
            raise ValueError("Only for-loops with a single name target are supported")
        range_args = self._parse_range(stmt.iter)
        if range_args is None:
            raise ValueError("Only for-loops over range(...) with constant bounds are supported")
        start, stop, step = range_args
        target = self._get_var(stmt.target.id)
        if stmt.orelse:
            raise ValueError("for-else is not supported")

        self.body.append(Assign(lhs=target, rhs=Constant(start, target.typ)))
        loop_head = self._new_label("loop_head")
        loop_end = self._new_label("loop_end")
        self.body.append(Location(labels=[loop_head]))

        cond = target < Constant(stop, target.typ) if step > 0 else target > Constant(stop, target.typ)
        exit_guard = Not(cond)
        goto_exit = Goto(guard=exit_guard, targets=[0])
        self._pending_gotos.append((goto_exit, loop_end))
        self.body.append(goto_exit)

        for inner in stmt.body:
            self._translate_stmt(inner)

        self.body.append(Assign(lhs=target, rhs=target + Constant(step, target.typ)))
        back_guard = Constant(0, SignedBVType(32)) != Constant(1, SignedBVType(32))
        goto_back = Goto(guard=back_guard, targets=[0])
        self._pending_gotos.append((goto_back, loop_head))
        self.body.append(goto_back)
        self.body.append(Location(labels=[loop_end]))

    def _translate_while(self, stmt: ast.While) -> None:
        if stmt.orelse:
            raise ValueError("while-else is not supported")
        loop_head = self._new_label("while_head")
        loop_end = self._new_label("while_end")
        self.body.append(Location(labels=[loop_head]))

        condition = self._translate_expr(stmt.test)
        exit_guard = Not(condition)
        goto_exit = Goto(guard=exit_guard, targets=[0])
        self._pending_gotos.append((goto_exit, loop_end))
        self.body.append(goto_exit)

        for inner in stmt.body:
            self._translate_stmt(inner)

        back_guard = Constant(0, SignedBVType(32)) != Constant(1, SignedBVType(32))
        goto_back = Goto(guard=back_guard, targets=[0])
        self._pending_gotos.append((goto_back, loop_head))
        self.body.append(goto_back)
        self.body.append(Location(labels=[loop_end]))

    def _translate_if(self, stmt: ast.If) -> None:
        cond = self._translate_expr(stmt.test)
        else_label = self._new_label("if_else")
        end_label = self._new_label("if_end")

        goto_else = Goto(guard=Not(cond), targets=[0])
        self._pending_gotos.append((goto_else, else_label))
        self.body.append(goto_else)

        for inner in stmt.body:
            self._translate_stmt(inner)

        if stmt.orelse:
            goto_end = Goto(guard=Constant(0, SignedBVType(32)) != Constant(1, SignedBVType(32)), targets=[0])
            self._pending_gotos.append((goto_end, end_label))
            self.body.append(goto_end)

            self.body.append(Location(labels=[else_label]))
            for inner in stmt.orelse:
                self._translate_stmt(inner)
            self.body.append(Location(labels=[end_label]))
        else:
            self.body.append(Location(labels=[else_label]))

    def _parse_range(self, expr: ast.expr):
        if not isinstance(expr, ast.Call) or not isinstance(expr.func, ast.Name):
            return None
        if expr.func.id != "range":
            return None
        args = expr.args
        if not args or len(args) > 3:
            return None
        values = []
        for arg in args:
            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, int):
                return None
            values.append(arg.value)
        if len(values) == 1:
            start, stop, step = 0, values[0], 1
        elif len(values) == 2:
            start, stop = values
            step = 1
        else:
            start, stop, step = values
        if step == 0:
            raise ValueError("range() step cannot be 0")
        return start, stop, step

    def _new_label(self, prefix: str) -> str:
        self._label_counter += 1
        return f"{prefix}_{self._label_counter}"


def translate_and_verify(source: str, *, show_output: bool = True):
    translator = PyToGoto()
    result = translator.translate(source)
    return verify(result.program, show_output=show_output, normalize=False)


if __name__ == "__main__":
    program = "x = 0\nassert x != 0\n"
    translate_and_verify(program, show_output=True)
