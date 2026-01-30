I want you to make a simple Python library for receiving and gnerating JSON from the CBMC / CPROVER ecosystem

- You have access to the source of CBMC in the folder cbmc/ . The json generation, ingesting, and goto datatype are avaiable in there.
- You have access to the cbmc command line tools. `cbmc
- Please generate test cases by dumping the json from simple example C programs using cbmc, goto-cc, goto-instrument. Look at their `--help`. Document other interesting commands in this files

- Some commands that may or may not be useful

```
    goto-cc examples/assertions.c -o outputs/assertions.gb
   goto-instrument --show-symbol-table --json-ui outputs/assertions.gb > outputs/goto_symbol_table.json
   goto-instrument --show-goto-functions --json-ui outputs/assertions.gb > outputs/goto_functions.json
     symtab2gb --goto-functions outputs/goto_functions_wrapped.json \
            --out outputs/from_json.gb \
            outputs/cbmc_symbol_table_wrapped.json
    cbmc --show-gotofunctions --json-ui

```

- I've noticed that sometimes an outer layer of json needs to be stripped going from one tool to another
- Parse these examples using the python library
- Use simple dataclasses
- Try to make an MVP of something that can be reingested. The full json format is very ocmplex, maybe overly so.
- Make tests that roundtrip and make sure that
- Write tests for everything you do
- ALWAYS run tests. Run `uvx ty check` and `uvx ruff check`

## Helpful tips / gotchas learned

- `GotoFunctionDef.return_type` must allow `EmptyType` (e.g. `__CPROVER_initialize`); keep it typed as `Type`.
- CBMC JSON uses:
  - unary minus id: `"unary-"`
  - boolean ops: `"and"` / `"or"`
  - bitwise ops: `"bitand"` / `"bitor"` / `"bitxor"`
  - boolean constants: `{"type":{"id":"bool"},"value":{"id":"true|false"}}`
- For boolean xor use `notequal` (CBMC ignores `bitxor` on bool).
- Dataclass `__eq__` can override expression-building; ensure `Expr` subclasses use `eq=False`.
- `Goto` targets are numeric location numbers. When building custom CFGs (loops/ifs), use `Location` + label resolution or set location numbers carefully; set `normalize=False` when you need exact targets.
- `__CPROVER_initialize` symbol/function must exist in the symtab for CBMC to run on generated goto.
- `printf` and other stdio calls require more system symbols; builder-only symtabs will fail without library support.
- Array indexing is supported via `expr[index]` and should be used in tests instead of helper `idx()` functions.
- Python translator now supports `if/else`, `for range(...)`, `while`, and array indexing; it emits explicit blocks + gotos (no unrolling).
- Ty/Ruff config: `pyproject.toml` has `[tool.ty.src] include=["src","tests"] exclude=["cbmc"]` and `[tool.ruff]` include/exclude. Use `uvx ty check` / `uvx ruff check`.
