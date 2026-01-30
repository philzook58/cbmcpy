# GOTO IR (CBMC JSON UI) – Ground Truth Notes

This is the minimal, source-backed shape for the JSON emitted by
`goto-instrument --show-goto-functions --json-ui`. The ground truth for
instruction kinds and JSON fields is in:

- `cbmc/src/goto-programs/goto_program.h`
- `cbmc/src/goto-programs/show_goto_functions_json.cpp`

## Instruction Kinds (Complete List)

From `enum goto_program_instruction_typet`:

- `GOTO` — branch, possibly guarded
- `ASSUME` — non-failing guarded self loop
- `ASSERT` — assertions
- `OTHER` — anything else
- `SKIP` — just advance the PC
- `START_THREAD` — spawn async thread
- `END_THREAD` — end current thread
- `LOCATION` — semantically like SKIP
- `END_FUNCTION` — exit point of a function
- `ATOMIC_BEGIN` — begin block without interleavings
- `ATOMIC_END` — end block without interleavings
- `SET_RETURN_VALUE` — set return value (no control-flow change)
- `ASSIGN` — assignment lhs:=rhs
- `DECL` — declare a local variable
- `DEAD` — end-of-life for a local
- `FUNCTION_CALL` — call a function
- `THROW` — throw exception
- `CATCH` — push/pop/enter handler
- `INCOMPLETE_GOTO` — goto with unresolved target

Notes from `goto_program.h` semantics:
- `GOTO` jumps to `targets` iff `guard` is true (multiple targets are deprecated).
- `SET_RETURN_VALUE` does not change control flow.
- `DECL`/`DEAD` bracket a local variable’s lifetime.

## JSON Shape (Functions + Instructions)

The JSON structure is produced by `show_goto_functions_json.cpp`:

```
{
  "functions": [
    {
      "name": "...",
      "isBodyAvailable": true|false,
      "isInternal": true|false,
      "isHidden": true|false,
      "parameterIdentifiers": ["..."],
      "instructions": [
        {
          "instructionId": "ASSIGN",
          "locationNumber": 12,
          "sourceLocation": {...},   // only if present
          "instruction": "...",      // human-readable text
          "code": {...},             // only if code is present
          "guard": {...},            // only if has_condition()
          "targets": [7, 9],         // only if non-empty
          "labels": ["..."]          // only if non-empty
        }
      ]
    }
  ]
}
```

Important details:
- `instructionId` is `instruction.to_string()` (matches the enum names).
- `locationNumber` is the numeric location for the instruction.
- `targets` are **locationNumber** values (not indices).

## Program Structure (Functions, Blocks, Control Flow)

CBMC’s GOTO IR is **not block-based** in the source model. A program is:

- `goto_modelt` = **symbol table** + **goto_functionst**
- `goto_functionst` = map of function name → `goto_programt`
- `goto_programt` = **linear list of instructions**

Control flow is encoded by:
- The **fallthrough** to the next instruction in the list.
- Explicit **GOTO** instructions that jump to `targets` (by location number).
- The `guard` on a GOTO provides conditional branching (there is no distinct
  “IF” instruction; IF/ELSE/loops are lowered to GOTO + guards).

So “basic blocks” are implicit: you can recover them by splitting the linear
instruction list at branch targets and branch instructions. When you serialize
with `--json-ui`, you only see the list + `targets` + `guard`, not explicit
block objects.

## Code/Guard IREPs

`code` and `guard` are JSON IREPs (see `util/json_irep.*`). For example,
assignment code uses `statement.id = "assign"` with `sub = [lhs, rhs]`.

## JSON UI Wrapper

`--json-ui` wraps outputs in a list of messages. Some tools want only the
inner payload (e.g., symbol table or goto functions), so you may need to strip
the outer list before feeding another tool.

## Symbol Table (symtab)

CBMC’s GOTO programs are interpreted together with a **symbol table**. The
symbol table records all symbols (types, globals, locals, functions) with their
types, optional values, and flags (e.g., static lifetime, parameter, lvalue).
The GOTO conversion pipeline consumes the symbol table, and many tools will
reject GOTO JSON if required symbols are missing (notably function symbols and
`__CPROVER_initialize`).

Ground truth JSON shape is in `cbmc/src/goto-programs/show_symbol_table.cpp`:
`--show-symbol-table --json-ui` emits a wrapper with a `"symbolTable"` object,
mapping symbol names to entries like:

```
{
  "symbolTable": {
    "c::main": {
      "prettyName": "...",
      "name": "c::main",
      "baseName": "main",
      "mode": "C",
      "module": "...",
      "prettyType": "...",
      "prettyValue": "...",
      "type": { ... },     // irep
      "value": { ... },    // irep (may be nil)
      "location": { ... },
      "isType": false,
      "isMacro": false,
      "isStaticLifetime": false,
      "isParameter": false,
      ...
    }
  }
}
```

### How to generate a symtab

From C sources:

```
goto-cc examples/foo.c -o outputs/foo.gb
goto-instrument --show-symbol-table --json-ui outputs/foo.gb > outputs/symtab.json
```

From existing GOTO JSON:
- Use `symtab2gb` with a symbol table JSON and a goto-functions JSON:
  `symtab2gb --goto-functions <functions.json> --out <out.gb> <symtab.json>`

## Useful Commands

- `goto-cc` → compile C to GOTO binary
- `goto-instrument --show-symbol-table --json-ui`
- `goto-instrument --show-goto-functions --json-ui`
- `symtab2gb --goto-functions <functions.json> --out <out.gb> <symtab.json>`
