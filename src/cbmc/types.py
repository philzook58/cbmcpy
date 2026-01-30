from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonUiMessage:
    message_type: str
    message_text: str
    data: dict[str, Any]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "JsonUiMessage":
        return cls(
            message_type=str(data.get("messageType", "")),
            message_text=str(data.get("messageText", "")),
            data=data,
        )

    def to_json(self) -> dict[str, Any]:
        return dict(self.data)


@dataclass(frozen=True)
class JsonUiDocument:
    program: str | None
    messages: list[JsonUiMessage]
    payloads: list[dict[str, Any]]
    raw: list[dict[str, Any]]

    def payload_by_key(self, key: str) -> dict[str, Any] | None:
        for payload in self.payloads:
            if key in payload:
                return payload
        return None

    def to_json_ui(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if self.program is not None:
            items.append({"program": self.program})
        items.extend(message.to_json() for message in self.messages)
        items.extend(self.payloads)
        return items


@dataclass(frozen=True)
class Symbol:
    name: str
    base_name: str | None
    pretty_name: str | None
    data: dict[str, Any]

    @classmethod
    def from_json(cls, name: str, data: dict[str, Any]) -> "Symbol":
        return cls(
            name=str(data.get("name", name)),
            base_name=data.get("baseName"),
            pretty_name=data.get("prettyName"),
            data=data,
        )


@dataclass(frozen=True)
class SymbolTable:
    symbols: dict[str, Symbol]
    data: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {"symbolTable": {name: symbol.data for name, symbol in self.symbols.items()}}


@dataclass(frozen=True)
class GotoInstruction:
    instruction_id: str | None
    location_number: int | None
    instruction: str | None
    labels: list[str]
    code: dict[str, Any] | None
    data: dict[str, Any]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GotoInstruction":
        return cls(
            instruction_id=data.get("instructionId"),
            location_number=data.get("locationNumber"),
            instruction=data.get("instruction"),
            labels=list(data.get("labels", [])),
            code=data.get("code"),
            data=data,
        )


@dataclass(frozen=True)
class GotoFunction:
    name: str
    instructions: list[GotoInstruction]
    is_body_available: bool | None
    is_hidden: bool | None
    is_internal: bool | None
    parameter_identifiers: list[str]
    data: dict[str, Any]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GotoFunction":
        instructions = [GotoInstruction.from_json(item) for item in data.get("instructions", [])]
        return cls(
            name=str(data.get("name", "")),
            instructions=instructions,
            is_body_available=data.get("isBodyAvailable"),
            is_hidden=data.get("isHidden"),
            is_internal=data.get("isInternal"),
            parameter_identifiers=list(data.get("parameterIdentifiers", [])),
            data=data,
        )


@dataclass(frozen=True)
class GotoFunctions:
    functions: list[GotoFunction]
    data: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {"functions": [fn.data for fn in self.functions]}
