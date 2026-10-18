# Project document layout

## 1. Directory map

- Canonical project document root: `<project-root>/docs/`.

- Directory guides: [artifact/](../../convention/references/artifacts.md),
  [lessons-learned/](lessons-learned.md), [original/](original.md),
  [refined/](refined.md) and [skills/](specification.md).

```text
docs/
├── artifact/
│   ├── output/
│   ├── media/
│   ├── data/
│   ├── model/
│   ├── software/
│   ├── interactive/
│   ├── evidence/
│   ├── release/
│   └── other/
├── lessons-learned/
│   ├── errors/<domain>-<name>/
│   └── judgment-differences/<domain>-<name>/
├── original/<domain>-<name>/
├── refined/
│   ├── analysis/<domain>-<name>/
│   ├── comparison/<domain>-<name>/
│   ├── history/<domain>-<name>/
│   ├── interview/<domain>-<name>/
│   └── research/<domain>-<name>/
└── skills/
    ├── design-<domain>-<name>/
    ├── info-<domain>-<name>/
    └── rule-<domain>-<name>/
```

## 2. Path notation and storage

- `<domain>` is the domain name. Outside `skills/`, use `none` when no domain applies.
- `skills/` requires a specific or shared domain; `none` is not allowed.
- `<name>` is the package name.
- Artifact domains contain files only; topic, date and version belong in filenames.
  Multi-file bundles are archives; see the artifact guide for classification and controls.
- Task progress and execution records reside only in Agent Factory runtime project
  storage, outside `docs/`.

<a id="rendering"></a>

## 3. Rendering in the Document viewer

- The extension's control-center Document viewer lists and renders Documents read-only.
  Write packages so they render without hand fixes:
- The list shows each package by its `SKILL.md` front-matter `name` and one-line
  `description`, and a standalone file (a lesson) by its `name` or first heading. Keep both present.
- Link sub-documents and assets with relative paths inside the project (or plugin) checkout.
  Absolute paths, `file://` links and paths that climb outside the checkout do not open.
- Cross-document anchors use a heading or an explicit `<a id="..."></a>` marker; keep an anchor
  stable once other Documents link to it.
- A diagram renders only as an Archify JSON asset whose name ends in `.architecture.json` or
  `.sequence.json`, linked from a list item or paragraph. The diagram appears right below that
  link; keep the meaning in the link's sentence as well. See [Diagrams](../../convention/references/diagrams.md#document-assets).
- Mermaid fences, raw HTML and images stay as code or links. Whole-line HTML comments are hidden.
- `metadata.yaml` and front matter appear folded as metadata, not as body text.
