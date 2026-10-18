# Document format

- Refined/Specification authors follow [Document core requirements](../SKILL.md) and this format.
  Original and Lessons Learned use their type guides.

<a id="document-package"></a>

## 1. Document package

### 1.1. Entry, references and package ownership

- Packages contain `SKILL.md`, optional detailed `references/` and optional `assets/`;
  no `scripts/` or `agents/`. A Refined `SKILL.md` does not activate it as a Skill.
- Keep overview, essential guidance and links stating when to read each topic at the entry.
  Split hard-to-read or maintain detail into coherent `references/*.md`, without size thresholds or duplication.
- Every reference MUST be reachable from `SKILL.md` through explicit relative Markdown links.
  Every asset MUST have a relative link/image at its point of use in the entry or a reachable
  reference. Optional folders may be absent; existing files must be linked. Read only needed links.
- Entry and references form one canonical package, sharing type, language, authority and
  provenance. Splitting creates neither a Specification nor a competing source.
- Apply the mandatory [Document structure](#document-structure) to Markdown bodies.

### 1.2. Assets and renderer representation

- Body and assets, including CSV/JSON, are editable sources. Store each JSON diagram,
  system architecture, database/ERD or API design as a separate `assets/*.json`.
  Reference it at use with a descriptive relative Markdown link, such as
  `[System architecture](assets/system-architecture.json)`. Never duplicate/embed its JSON in Markdown.
- Store independent CSV datasets and needed images in `assets/` too. Expanded asset displays
  are derived, not editable peers. Do not assume a renderer; follow
  [Diagrams](../../convention/references/diagrams.md) for formats and readable text.

<a id="document-structure"></a>

## 2. Document structure

- Use only `# Title`, `## 1. Section`, `### 1.1. Subsection`: unnumbered title, numbered
  sections/subsections with trailing periods. Split topics needing deeper headings.
- Group headings and references by [topic and purpose](../../convention/references/prompting.md#section-scope).
- MUST apply [wording and revision](../../convention/references/prompting.md#concise-wording),
  including language-specific forms. Bodies use lists, blocks or tables; indent mixed nested lists.
- Use Markdown tables and [section-final visual placement](../../convention/references/prompting.md#section-table-order)
  for tables, figures, images, shapes and diagrams.
- Use native Markdown for code blocks/images; structured design JSON follows
  the linked-asset [package contract](#document-package).

<a id="naming-and-metadata"></a>

## 3. Naming and metadata

- Follow [layout](layout.md) and the type guide for names/categories. Preserve identities;
  never infer domains or bulk-rename accepted Documents.
- Refined/Specification YAML records `document-type`, `category`, `domain`, `name`, applicable
  `language` and actual provenance. Undefined domain: `null`. Metadata grants no authority.
- Project Specifications keep management fields in `metadata.yaml` and discovery fields
  (`name`, `description`) in `SKILL.md` front matter. Read management metadata only for
  classification, provenance or authority evidence, not routine instructions or Markdown display.
- Preserve every field when extracting legacy inline metadata; it remains readable.
  Keep one metadata source. Existing Refined packages need no conversion. Installed capability
  Skills, Original, legacy Progress and Lessons Learned retain their representations.
