# Specification (Skill document) writing

<a id="authority-and-scope"></a>

## 1. Authority and scope

- Apply [Document requirements](../SKILL.md). Specification document and Skill document are synonymous.
  Only the Human's explicit request grants Specification authority;
  generation, format and inferred approval do not.
- A Skill document MUST present the current accepted state as a self-contained reference,
  including reasons and unresolved choices. Readers must not reconstruct it from past revisions.
  Apply the [current/history boundary](#current-and-history).
- Keep external source URLs with access identification and the minimal Human authorization
  pointers on which the current rule depends. Preserve source evidence in Original documents.
- Before removing a run ID, read its source request or contract. When it is the only
  evidence of a current authorization or an external source, keep or relocate that
  pointer first; never bulk-delete references. Past records found by search are
  evidence, not current authority or active rules.

<a id="current-and-history"></a>

### 1.1. Current rules and historical records

- Revise the owning current clause; do not append a chronological update log.
  Move unique superseded content with its source, anchors and references preserved;
  keep current limitations and unresolved decisions in the current document.
- History links support targeted lookup, not routine loading. Preserve explicit required
  historical evidence; never infer approval, completion or a current rule from an archive alone.

| Current Specification | Historical record |
| --- | --- |
| Accepted behaviour, applicable scope, conditions, exceptions and unresolved choices | Superseded designs, dated implementation/check reports, run/lesson ID lists and old source layouts |
| Current detailed rules in linked references | Source-faithful material in Refined `history`; execution details in their existing runtime records |
| Minimal source/authorization pointers and explicit observation freshness | Full past discussion and evidence; no automatic current-rule authority |

<a id="specification-naming"></a>

## 2. Specification naming

- Specification categories are limited to `info-*`, `rule-*`, and `design-*`.

- Keep planning intent and implementation design for the same subject in `design`; do
  not add `plan` or `spec` categories. Design includes behavior, not only
  styling.

| Category | How to write | Example |
|---|---|---|
| `info` | State known facts and their scope; distinguish observations from assumptions. | “The extension host owns session persistence.” |
| `rule` | State who or what must do what, under which condition; include accepted exceptions. | “When submitting an answer, the client must include the question ID.” |
| `design` | State the intended behavior, relevant flow and boundaries; include implementation design only where decided. | “Selecting an option sends its answer immediately, without confirmation.” |

<a id="writing-procedure"></a>

## 3. Writing procedure

1. Identify the subject, applicable scope, accepted content and unresolved decisions.
2. Group related content using the mandatory [Document structure](format.md#document-structure). Include only useful sections;
   do not create empty purpose, history, glossary or implementation sections.
3. Write one fact, obligation or design decision per item, using the category above.
   Retain conditions, exceptions and observable outcomes that affect interpretation.
4. Use Markdown tables for comparisons, numbered lists for ordered behavior and JSON for
   blocks. Indent mixed nested lists. Keep examples separate from requirements; examples
   must not introduce new rules.
5. Integrate revisions into the affected clauses and remove superseded duplication. Put
   unresolved choices in a clearly marked section only when they exist; never fill gaps
   with invented requirements or claim implementation completion.
6. Review coverage against the accepted content: no missing conditions, contradictory
   clauses, ambiguous subjects or new decisions. Resolve conflicting accepted meaning
   with the Human; a Refined comparison may support that decision without authority.

<a id="package-and-derived-copies"></a>

## 4. Package and derived copies

- Use the [directory layout](layout.md) for paths and [Document format](format.md)
  for entry files, references, assets, language and metadata.
- Update the canonical source and regenerate `.codex/skills/`, `.claude/skills/`, `.agents/skills/` or displays from it. Do not
  require an English translation, paired HTML, counterpart metadata or a two-source
  synchronization transaction. A stale copy gains no competing authority.
