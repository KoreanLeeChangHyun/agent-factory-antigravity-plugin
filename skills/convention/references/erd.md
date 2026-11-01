# ERD JSON and rendering

## 1. Source and renderer

- Use `diagram_type: "erd"`, `schema_version: 1` and filenames ending in `.erd.json`
  (or `.archify.json`). Store originals in `docs/artifact/diagram/` and link them from
  Documents with relative Markdown links. Do not duplicate the JSON in a Document package.
- This is the bundled Agent Factory ERD renderer v1, not an official Archify schema or
  conversion into architecture nodes. It needs Python only; no renderer download,
  database connection, Mermaid dependency or Node process is required for ERD.
- The machine schema is `<plugin-root>/runtime/system/erd.schema.json`; the renderer
  additionally checks graph references, uniqueness and nonnullable primary keys.
  Existing arbitrary ERD JSON is not automatically compatible; preserve its source and
  explicitly map it to this documented schema before claiming support.

## 2. JSON contract

- Required root fields: `schema_version`, `diagram_type`, `meta`, `entities`, `relationships`.
  Unknown fields are rejected. `meta.title` is required. Optional `meta.output` is descriptive
  only; `--output` exclusively selects a standalone HTML destination.
- `entities`: a nonempty array of objects with a unique nonempty `id`, optional display
  `label` and an `attributes` array. Empty attributes support conceptual entities.
- Attributes require a unique `name` within their entity and a nonempty display `type`.
  Optional `keys` contains unique `PK`, `FK`, `UK` values, including combined `PK`/`FK`.
  Optional boolean `nullable` displays `NULL` or `NOT NULL`; omission makes no nullability
  claim. A primary key cannot explicitly be nullable. Types are labels, not executable SQL.
- Relationships require `from`, `to`, `from_cardinality`, `to_cardinality`. Both entities
  must exist. Optional `from_attribute` and `to_attribute` must name existing fields;
  they select field ports when endpoints are adjacent in the same row.
- Cardinalities describe the endpoint they name: `1` exactly one, `0..1` zero or one,
  `1..*` one or more, `0..*` zero or more. For User→Order with one User per Order and
  zero or more Orders per User, use `from_cardinality: "1"`, `to_cardinality: "0..*"`.
- Optional relationship fields: unique `id`, display `label` and boolean `identifying`.
  Explicit `true` draws solid, explicit `false` dashed; omission makes no identifying
  claim and uses a solid display line. Self-references, parallel relationships and
  disconnected entities are retained. Keys and cardinalities are never inferred.
- Optional `layout.columns` is a positive integer. Otherwise layout uses a deterministic
  grid. Tables expand to retain authored fields and Unicode labels; large diagrams can
  require zoom/pan. No entities or relationships are silently dropped.
- Keys and cardinalities follow familiar [crow's foot notation](https://mermaid.js.org/syntax/entityRelationshipDiagram.html#relationship-syntax).

## 3. Views and CLI

- Document links show the inert SVG preview. Choosing the preview opens the same JSON in
  the independent diagram view. Saving the original refreshes both views.
- The ERD view offers source editing, refresh, zoom, pan, fit and SVG export; it follows
  the VS Code light/dark theme. Focus the diagram and use `+`, `-`, `0`/`Home` for zoom/fit.
  Wheel input retains normal host behavior. SVG export defaults to `artifact/media/`.
- The independent ERD view uses only bundled nonce-protected scripts and inert SVG data
  images. Labels are escaped; external resources and authored scripts are not executed.
- `preview` accepts JSON on stdin and returns SVG/styles; `--viewer` is accepted but ERD
  uses the extension's bundled viewer, so the response contains no official viewer HTML.
- ERD validate/render do not require `--tool-dir`. Invalid JSON/graph/schema fails before
  publishing; existing files are never overwritten. Standalone HTML is self-contained and
  static; extension zoom/pan controls are not embedded in that HTML.

```sh
python3 <plugin-root>/scripts/archify.py validate --project-root <project-root> docs/artifact/diagram/example__v1.erd.json
python3 <plugin-root>/scripts/archify.py render --project-root <project-root> docs/artifact/diagram/example__v1.erd.json --output docs/artifact/interactive/example-erd__v1.html
```
