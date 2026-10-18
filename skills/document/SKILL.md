---
name: document
description: Author, revise, classify, search, migrate or synchronize project Documents and their canonical sources.
metadata:
  specification-id: document
---

# Agent Factory Document

- Applies to project Documents; installed capabilities keep their own format.
- `<plugin-root>` is two levels above this file and contains `skills/`, `runtime/`, `scripts/`.

<a id="mandatory-compliance"></a>

## 1. Core requirements

- Authoring requires the selected [guides](#writing-guides) and [check](#authoring-check);
  catalog, search, reading and synchronization need no authoring guides or check.
- Preserve accepted decisions, unresolved choices, fidelity and authority. Document operations
  grant neither approval nor Specification authority.
- Use the Human's or selected language. Preserve source text, quotations, code, identifiers
  and Original metadata/link strings exactly; language selection grants no translation authority.
- Keep Specifications self-contained and current. Superseded discussions/decisions belong in
  Refined history and source evidence in Original. Task progress, status and execution records
  belong only in Agent Factory runtime storage.
- After `docs/skills/` creation, modification or deletion, run [synchronization](references/host-sync.md#continuous-codex-synchronization)
  for the actual project. Resolve or report conflicts before claiming success.

<a id="authoring-check"></a>

### 1.1. Authoring check

- For authoring, MUST apply the [authoring check](references/authoring-check.md#authoring-check) before writing and before completion.

<a id="writing-guides"></a>

## 2. Operation guides

- Read only the selected operation's guides and mandatory dependencies; reuse current supplied guidance.
- Authoring requires the selected type guide below and applicable [format](#naming-and-metadata).
  Work contract content uses the matching preparation/execution section of
  [work contracts](../convention/references/work-contracts.md).
- Use [section 6](#host-sync) for discovery/host operations and [layout](references/layout.md)
  for path decisions. Reuse bound paths and rules.
- [Convention](../convention/SKILL.md): development, themes, diagrams, interviews;
  [Agent](../agent/SKILL.md): managed execution.

<a id="types-and-authority"></a>

## 3. Types and authority

- Every AI-generated durable Document is Refined by default unless the Human explicitly
  requests a Specification. Errors/judgment differences use Lessons Learned instead.
- Only these types apply. `Original -> Refined -> Specification (Skill)` is optional provenance,
  not a pipeline, maturity scale or promotion; preserve actual relationships.

| Type and required guide | Meaning |
|---|---|
| [Original](references/original.md) | Self-contained, source-faithful metadata/links to external evidence. |
| [Refined](references/refined.md) | Non-authoritative analysis, research, interview, comparison or history; compatibility type `processed`. |
| [Lessons Learned](references/lessons-learned.md) | Error causes/solutions or Human/AI judgment differences and reflection; no Specification authority. Only the matching capture/lifecycle section applies, within role limits. |
| [Specification](references/specification.md) (Skill document) | Explicitly Human-requested current facts, rules or designs; both names are synonymous. |

<a id="routing"></a>

## 4. Storage and migration

<!-- clause-id: specification.routing.canonical -->
- Keep one editable source under [layout](references/layout.md). Local storage is complete standalone
  behavior, not an error fallback; other destinations/formats are derived exports.
- Preserve existing Documents and unmanaged Skills. Only explicit requests authorize
  [migration](references/migration.md), moves or replacements; preserve content, identities,
  language, provenance and unresolved choices. Resolve collisions before sync; collisions grant no replacement authority.
- Standalone non-Document deliverables follow [Artifacts](../convention/references/artifacts.md).

<a id="document-package"></a>
<a id="document-structure"></a>
<a id="naming-and-metadata"></a>

## 5. Format and metadata

- [Format](references/format.md) owns Refined/Specification structure and metadata.
  Original and lesson actions use their type guides without a `SKILL.md` wrapper.

<a id="host-sync"></a>

## 6. Export, synchronization and discovery

- Reading/search/export preserve type and authority. For selective reads, use catalog/search
  [paths, anchors and revisions](references/catalog-search.md#13-matching-and-source-revision).

| Next operation | Guide/section |
|---|---|
| One-time project Skill export | [Host export](references/host-sync.md#explicit-codex-export) |
| Sync/check/reconcile owned copies | [Host synchronization](references/host-sync.md#continuous-codex-synchronization) |
| Catalog/search/read canonical Documents | [Catalog and search](references/catalog-search.md#local-document-catalog-and-search) |
| Main: prepare requested document-dependent execution | [Request-bound retrieval](references/catalog-search.md#request-context) |
| Authorized path migration/layout conversion | [Migration](references/migration.md); type guides only for representation changes |

<a id="installed-capability-boundary"></a>
<a id="boundaries"></a>

## 7. Ownership boundaries

- Sync only declared project roots; preserve installed capabilities and unmanaged Skills.
- Honor assigned files and captured roles; standalone Document work needs no managed role.
  Shared summaries/catalogs have one owner or managed CLI.
- Apply only bound [role exceptions](../agent/references/role-exceptions.md#assigned-records),
  without loading every execution mode or role prompt for ordinary authoring.
- Own records grant no Specification adoption, publication, control of others' records
  or unrelated migration/deletion authority.
