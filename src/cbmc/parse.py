from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import (
    GotoFunction,
    GotoFunctions,
    JsonUiDocument,
    JsonUiMessage,
    Symbol,
    SymbolTable,
)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_json_ui(data: Any) -> JsonUiDocument:
    if not isinstance(data, list):
        raise TypeError("JSON UI data must be a list of objects")
    program = None
    messages: list[JsonUiMessage] = []
    payloads: list[dict[str, Any]] = []
    raw_items: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_items.append(item)
        if "program" in item:
            program = str(item.get("program"))
            continue
        if "messageType" in item or "messageText" in item:
            messages.append(JsonUiMessage.from_json(item))
            continue
        payloads.append(item)
    return JsonUiDocument(program=program, messages=messages, payloads=payloads, raw=raw_items)


def strip_json_ui(data: Any, key: str | None = None) -> Any:
    if isinstance(data, list):
        doc = parse_json_ui(data)
        if key is not None:
            payload = doc.payload_by_key(key)
            if payload is None:
                raise KeyError(f"Missing payload with key '{key}'")
            return payload
        if len(doc.payloads) == 1:
            return doc.payloads[0]
        return doc.payloads
    return data


def parse_symbol_table(data: Any) -> SymbolTable:
    payload = strip_json_ui(data, key="symbolTable") if isinstance(data, list) else data
    if not isinstance(payload, dict) or "symbolTable" not in payload:
        raise ValueError("Expected a 'symbolTable' payload")
    symtab = payload["symbolTable"]
    if not isinstance(symtab, dict):
        raise TypeError("symbolTable must be a JSON object")
    symbols = {name: Symbol.from_json(name, value) for name, value in symtab.items()}
    return SymbolTable(symbols=symbols, data=payload)


def parse_goto_functions(data: Any) -> GotoFunctions:
    payload = strip_json_ui(data, key="functions") if isinstance(data, list) else data
    if not isinstance(payload, dict) or "functions" not in payload:
        raise ValueError("Expected a 'functions' payload")
    functions = payload["functions"]
    if not isinstance(functions, list):
        raise TypeError("functions must be a JSON array")
    parsed = [GotoFunction.from_json(item) for item in functions if isinstance(item, dict)]
    return GotoFunctions(functions=parsed, data=payload)


def wrap_json_ui(payload: dict[str, Any], program: str = "cbmc-json3") -> list[dict[str, Any]]:
    return [{"program": program}, payload]


def dump_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def parse_c_file(
    c_path: str,
    output_dir: str | None = None,
    *,
    goto_cc: str = "goto-cc",
    goto_instrument: str = "goto-instrument",
) -> tuple[SymbolTable, GotoFunctions]:
    c_file = Path(c_path)
    if not c_file.exists():
        raise FileNotFoundError(c_path)

    out_dir = Path(output_dir) if output_dir is not None else c_file.parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    gb_path = out_dir / f"{c_file.stem}.gb"
    symtab_path = out_dir / f"{c_file.stem}_symbol_table.json"
    functions_path = out_dir / f"{c_file.stem}_goto_functions.json"

    _run_command([goto_cc, str(c_file), "-o", str(gb_path)])
    _run_command(
        [goto_instrument, "--show-symbol-table", "--json-ui", str(gb_path)],
        stdout_path=symtab_path,
    )
    _run_command(
        [goto_instrument, "--show-goto-functions", "--json-ui", str(gb_path)],
        stdout_path=functions_path,
    )

    symbol_table = parse_symbol_table(load_json(str(symtab_path)))
    goto_functions = parse_goto_functions(load_json(str(functions_path)))
    return symbol_table, goto_functions


def _run_command(args: list[str], stdout_path: Path | None = None) -> None:
    import subprocess

    if stdout_path is None:
        subprocess.run(args, check=True)
        return
    with open(stdout_path, "w", encoding="utf-8") as handle:
        subprocess.run(args, check=True, stdout=handle)
