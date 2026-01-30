from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ir import SourceLocation, Type


@dataclass(frozen=True)
class SymbolEntry:
    name: str
    base_name: str
    typ: Type
    location: SourceLocation
    module: str = "generated"
    mode: str = "C"
    pretty_name: str | None = None
    value: dict[str, Any] | None = None
    is_type: bool = False
    is_macro: bool = False
    is_exported: bool = False
    is_input: bool = False
    is_output: bool = False
    is_state_var: bool = False
    is_property: bool = False
    is_static_lifetime: bool = False
    is_thread_local: bool = False
    is_lvalue: bool = True
    is_file_local: bool = False
    is_extern: bool = False
    is_volatile: bool = False
    is_parameter: bool = False
    is_auxiliary: bool = False
    is_weak: bool = False

    def to_json(self) -> dict[str, Any]:
        data = {
            "type": self.typ.to_json(),
            "location": self.location.to_json(),
            "name": self.name,
            "module": self.module,
            "baseName": self.base_name,
            "mode": self.mode,
            "prettyName": self.pretty_name or self.base_name,
            "isType": self.is_type,
            "isMacro": self.is_macro,
            "isExported": self.is_exported,
            "isInput": self.is_input,
            "isOutput": self.is_output,
            "isStateVar": self.is_state_var,
            "isProperty": self.is_property,
            "isStaticLifetime": self.is_static_lifetime,
            "isThreadLocal": self.is_thread_local,
            "isLvalue": self.is_lvalue,
            "isFileLocal": self.is_file_local,
            "isExtern": self.is_extern,
            "isVolatile": self.is_volatile,
            "isParameter": self.is_parameter,
            "isAuxiliary": self.is_auxiliary,
            "isWeak": self.is_weak,
        }
        if self.value is not None:
            data["value"] = self.value
        return data


@dataclass
class SymbolTableBuilder:
    symbols: dict[str, SymbolEntry] = field(default_factory=dict)

    def add(self, entry: SymbolEntry) -> None:
        self.symbols[entry.name] = entry

    def add_function(
        self,
        name: str,
        typ: Type,
        location: SourceLocation,
        *,
        module: str = "generated",
        mode: str = "C",
        is_extern: bool = False,
        is_lvalue: bool = True,
        is_static_lifetime: bool = False,
        is_file_local: bool = False,
    ) -> None:
        entry = SymbolEntry(
            name=name,
            base_name=name,
            typ=typ,
            location=location,
            module=module,
            mode=mode,
            pretty_name=name,
            value={"id": "compiled"},
            is_lvalue=is_lvalue,
            is_extern=is_extern,
            is_static_lifetime=is_static_lifetime,
            is_file_local=is_file_local,
        )
        self.add(entry)

    def add_local(
        self,
        identifier: str,
        base_name: str,
        typ: Type,
        location: SourceLocation,
        *,
        module: str = "generated",
        mode: str = "C",
    ) -> None:
        entry = SymbolEntry(
            name=identifier,
            base_name=base_name,
            typ=typ,
            location=location,
            module=module,
            mode=mode,
            pretty_name=base_name,
            is_lvalue=True,
        )
        self.add(entry)

    def to_payload(self) -> dict[str, Any]:
        return {"symbolTable": {name: entry.to_json() for name, entry in self.symbols.items()}}
