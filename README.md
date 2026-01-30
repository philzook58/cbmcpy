# cbmcpy

Small Python helpers for parsing and generating CBMC / CPROVER JSON UI payloads.

This is an MVP aimed at letting you:

- extract symbol tables and goto-functions from CBMC JSON
- generate goto programs via a Python builder API
- re-ingest JSON with `symtab2gb` and run `cbmc`
- translate small Python snippets to goto programs

The library assumes the CBMC toolchain (`cbmc`, `goto-cc`, `goto-instrument`, `symtab2gb`)
is available on your PATH.

## Install / import

Install from GitHub with uv:

```bash
uv pip install git+github.com:philzook58/cbmcpy.git
```

## Quick start: high-level builder API

This example builds a tiny program, runs CBMC, and prints a counterexample:

```python
from cbmc import *

x = Signed("x", 64)
prog = GotoProgram([Assign(x, 0), Assert(x != 0)])

verify(prog, show_output=True)  # prints CBMC output + trace
```

## Ergonomic builder helpers

Some conveniences mirror z3py-style usage:

```python
from cbmc import *

x = Signed("x", 32)
y = Signed("y", 32)

Assert( (x < y) & (y > 0) )
Assert( (x < 0) | (y > 0) )
Assert( (x == 1) ^ (y == 1) )   # boolean xor
Assign(x, -x)                    # unary minus

arr = Array("a", SignedBVType(32), 4)
Assign(arr[0], Constant(1, SignedBVType(32)))
```

## Example: explicit loop blocks (for-loop)

This uses explicit GOTO targets to represent a loop:

```python
from cbmc import *

i = Signed("i", 32)
n = Signed("n", 32)
total = Signed("sum", 32)

body = [
    Decl(symbol=total, location_number=1),
    Decl(symbol=i, location_number=2),
    Decl(symbol=n, location_number=3),
    Assign(n, Constant(4, i.typ)),
    Assign(total, Constant(0, i.typ)),
    Assign(i, Constant(1, i.typ)),
    Goto(guard=Not(i <= n), targets=[11], location_number=7),
    Assign(total, total + i),
    Assign(i, i + Constant(1, i.typ)),
    Goto(guard=(Constant(0, i.typ) != Constant(1, i.typ)), targets=[7], location_number=10),
    Assert(Not(total != Constant(10, i.typ))),  # 1+2+3+4 == 10
    SetReturnValue(value=Constant(0, i.typ), location_number=12),
    EndFunction(location_number=13),
]

prog = GotoProgram(body)
verify(prog, normalize=False)
```

When you set `normalize=False`, the builder will not insert extra declarations or
return/end-function instructions. This lets you fully control the block layout
and GOTO targets.

## Python-to-goto translation (experimental)

Translate simple Python into goto blocks and run CBMC:

```python
from cbmc import translate_and_verify

program = """
sum = 0
for i in range(1, 5):
    sum = sum + i
assert sum == 10
"""

translate_and_verify(program, show_output=True)
```

Supported (MVP): assignments, asserts, `if/else`, `for range(...)`, `while`,
basic arithmetic/compare, and array indexing via `a[i] = ...` with list literals.

## JSON UI envelope

Many CBMC tools produce a JSON UI list that wraps the payload:

```json
[
  {"program": "goto-instrument"},
  {"messageType": "STATUS-MESSAGE", "messageText": "..."},
  {"symbolTable": {"...": "..."}}
]
```

Some tools expect the inner payload directly (for example `symtab2gb`). Use
`strip_json_ui()` to drop the envelope, and `wrap_json_ui()` to add it back.

Example re-ingest flow:

```python
from cbmc import load_json, strip_json_ui, dump_json

symtab = strip_json_ui(load_json("outputs/assertions_symbol_table.json"), key="symbolTable")
funcs = strip_json_ui(load_json("outputs/assertions_goto_functions.json"), key="functions")

dump_json("outputs/assertions_symbol_table_stripped.json", symtab)
dump_json("outputs/assertions_goto_functions_stripped.json", funcs)
```

```bash
symtab2gb --goto-functions outputs/assertions_goto_functions_stripped.json \
  --out outputs/from_json.gb \
  outputs/assertions_symbol_table_stripped.json
```

## Parse existing CBMC JSON

```python
from cbmc import load_json, parse_symbol_table, parse_goto_functions, strip_json_ui

symtab_doc = load_json("outputs/assertions_symbol_table.json")
symtab = parse_symbol_table(symtab_doc)
raw_symtab_payload = strip_json_ui(symtab_doc, key="symbolTable")

functions_doc = load_json("outputs/assertions_goto_functions.json")
functions = parse_goto_functions(functions_doc)
```

## Generate example JSON with CBMC tools

```bash
mkdir -p outputs

goto-cc examples/assertions.c -o outputs/assertions.gb
goto-cc examples/arith.c -o outputs/arith.gb

goto-instrument --show-symbol-table --json-ui outputs/assertions.gb > outputs/assertions_symbol_table.json
goto-instrument --show-goto-functions --json-ui outputs/assertions.gb > outputs/assertions_goto_functions.json

goto-instrument --show-symbol-table --json-ui outputs/arith.gb > outputs/arith_symbol_table.json
goto-instrument --show-goto-functions --json-ui outputs/arith.gb > outputs/arith_goto_functions.json
```

## Commands from --help (selected)

CBMC (`cbmc --help`):

- `--show-properties`, `--show-symbol-table`, `--show-goto-functions`
- `--trace`, `--stop-on-fail`, `--property <id>`
- `--export-symex-ready-goto <file>`

Goto-cc (`goto-cc --help`):

- `--function <name>` to set entry point
- `--native-compiler <cmd>`, `--native-linker <cmd>`

Goto-instrument (`goto-instrument --help`):

- `--show-symbol-table`, `--show-goto-functions`, `--dot`
- `--list-goto-functions`, `--print-internal-representation`
- `--validate-goto-model`, `--interpreter`

Symtab2gb (`symtab2gb --help`):

- `--out <file>` to write a goto-binary
- `--goto-functions <file>` to merge JSON-encoded functions

## Tests

```bash
uvx ty check
uvx ruff check
pytest -q
```
