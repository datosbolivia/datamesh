---
name: technical-reference-comments
description: >
  Authoritative guide for the in-file comments and docstrings that form the
  canonical technical reference of the DataMesh SDK. Use when creating or
  editing any Python, Go, TypeScript, or R source file — public ports, use
  cases, adapters, domain models, value objects, or any symbol cited from
  docs/reference and CASOS_DE_USO.md.
license: MIT
---

# Technical Reference Comments

In-file documentation is the technical reference of this SDK. It lives with the code, ships with it, and is reviewed with it. `docs/reference/*` describes the contracts; the file itself must state them. A symbol without a documentation block is an undocumented contract and an error under the AGENTS.md documentation mandate.

## Iron Rule

Every exported symbol — public function, class, struct, interface, port, use case, adapter, and domain value object — carries a documentation block that states its contract: purpose, inputs, outputs, errors, and the OKF/ODKF invariant it enforces. No exported symbol without a block. Keep the block one line longer than the truth; never more.

## Per-Language Format

| Language   | Block                     | Scope                                                          |
| ---------- | ------------------------- | ------------------------------------------------------------- |
| Python     | Docstring (Google style)  | Module, class, public function: `Args` / `Returns` / `Raises`  |
| Go         | `//` doc comment          | Above every exported identifier, starting with its own name; package comment |
| TypeScript | JSDoc `/** ... */`        | Exported symbols: `@param` / `@returns` / `@throws` / `@example` |
| R          | roxygen `#'`              | Exported `dm_*` / `datamesh_*` functions: `@param` / `@return` / `@export` |

## What Every Block Must Contain

1. **Summary** — one line, third person, ends in a period.
2. **Contract** — parameters and return shape, or the fields a struct/type exposes.
3. **Errors** — every `raise`, `panic`, or thrown error, with its trigger.
4. **Normative reference** — OKF v0.2 `PE1`-`PE5` / `OE1`-`OE5`, an ADR number, or a standard (`W3C DCAT v3`, `ISO 19115`, `ISO 8601`, `PROV-O`, `SKOS`). Cite only references that are actually implemented.
5. **Canonical triad** — when the symbol addresses `[catalogo:]dataset:recurso`.

## The Why, Not the What

- Document invariants, side effects, trust-boundary validation, normalization, and non-obvious choices.
- Never restate the code. No narration of obvious assignments or control flow.
- Known limits carry the marker `shortcut: <the limit>, <when to upgrade>`.
- Keep domain terms exactly as the ubiquitous language defines them: `DataProduct`, `ResourceTriad`, `Contract`, `QualityProfile`, `Lineage`.

## Sync With the Reference

A public-contract change updates the block **and** the matching entry in `docs/reference/CASOS_DE_USO.md` and `docs/reference/ARQUITECTURA.md` in the same change. Reference the specification by section; never copy its text into a comment.

## Language

- Identifiers and code: English.
- Documentation blocks: English, matching the surrounding file.
- User-facing docs (`docs/`, `README.md`): Spanish.
- Never cite a spec section or triad the code does not implement.

## Examples

Python:

```python
def parse_dataproduct(uri_or_path: str) -> DataProduct:
    """Resolve and validate one OKF v0.2 Data Product.

    Args:
        uri_or_path: Node URI, local path, or canonical triad.

    Returns:
        The validated domain DataProduct.

    Raises:
        ValidationError: Mandatory frontmatter (type, dimensions) is missing.

    References:
        OKF v0.2 PE2 (mandatory type); ADR 0007 (manifest abstraction).
    """
```

Go:

```go
// ParseTriad decodes a canonical "[catalog:]dataset:resource" triad into its parts.
// Catalog is empty when omitted. It returns an error for malformed segments.
//
// Reference: OKF v0.2 canonical triad; ADR 0003.
func ParseTriad(raw string) (ResourceTriad, error) {
```

TypeScript:

```typescript
/**
 * Executes an ANSI SQL query over canonical triads.
 * @param sql - SQL text with 'catalogo:dataset:recurso' table names.
 * @returns Rows, columns, and the engine used.
 * @throws DataMeshError when a triad cannot be resolved.
 */
export async function sql(sql: string): Promise<QueryResult> {
```

R:

```r
#' Execute an ANSI SQL query over canonical triads.
#' @param query SQL text using canonical triad table names.
#' @return A data.frame with the result rows.
#' @export
dm_sql <- function(query) {
```

## Checklist Before Finishing

- [ ] Every new or changed exported symbol has a block.
- [ ] Error cases named in the block are the ones actually thrown.
- [ ] Every normative reference (`PE`/`OE`/ADR/standard) is real.
- [ ] No comment restates code.
- [ ] Public contracts mirror `docs/reference`.
