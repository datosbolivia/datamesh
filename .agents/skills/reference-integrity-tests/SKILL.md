---
name: reference-integrity-tests
description: >
  Verify that the publicly documented reference of the DataMesh SDK stays in
  sync with the real code: exported Python API, CLI subcommands, ports,
  adapters and use cases named in docs/reference/ must exist and resolve.
  Use after refactors of bindings/, before releases, when docs/reference/
  or CASOS_DE_USO.md changes, or on "verify the docs are true" requests.
---

Keeps the promise of AGENTS.md section 1: no orphan code, no phantom API.
The reference is normative; a documented symbol that no longer exists is a
contract break for users. This skill checks the contract cheaply.

## 1. What to run

- `python3 -m pytest -q bindings/python/tests/test_reference_integrity.py`
  from the repo root or `bindings/python`. It asserts:
  - every name in `datamesh.__all__` resolves via `hasattr`;
  - every documented public API name (`docs/reference/CASOS_DE_USO.md`,
    `README.md`, `bindings/python/datamesh/__init__.py`) is exported;
  - every documented CLI subcommand appears in `python -m datamesh.cli`
    usage output.
- If `bindings/python/datamesh` cannot be imported, stop and report it:
  that is a break, not a test problem.

## 2. When the test fails

1. Confirm the symbol truly vanished: `rg "def <name>|class <name>"` in
   `bindings/python/datamesh/`.
2. Decide in this order:
   - keep it if it is public and used elsewhere (ports, use cases, docs);
   - remove it from `__all__` and from the docs *only* if it is internal;
   - otherwise re-export the symbol (alias) — this is the cheapest fix.
3. Update the source of truth: `docs/reference/CASOS_DE_USO.md` and
   `docs/reference/ARQUITECTURA.md`. Never edit the test to hide a break.

## 3. Extending the contract

- New top-level function in `datamesh/__init__.py`? Add it to
  `DOCUMENTED_API` in the test and to `docs/reference/CASOS_DE_USO.md`.
- New CLI subcommand in `datamesh/cli.py`? Add it to
  `DOCUMENTED_CLI_COMMANDS` in the test.
- New port, adapter or use case? It is covered by `hasattr(__all__)`, but
  still document it in `CASOS_DE_USO.md` / `ARQUITECTURA.md` (AGENTS.md §1).

## 4. Checklist before finishing

- [ ] `test_reference_integrity.py` passes
- [ ] full suite passes: `python3 -m pytest -q bindings/python/tests`
- [ ] `docs/reference/` mentions match the exported symbols
- [ ] no documented symbol removed without a re-export or a doc update

Keeps the contract honest; changes nothing else.