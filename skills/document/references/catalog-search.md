# Local document catalog and search

<a id="local-document-catalog-and-search"></a>

## 1. Catalog and search

### 1.1. Catalog discovery and roots

- Specification packages use the host Skill catalog. Original, Refined and Lessons Learned
  use this Skill's local Document catalog. Legacy progress records remain discoverable.
- Run `<plugin-root>/scripts/catalog_documents.py --project-root <project-root>` to emit a current JSON
  catalog of canonical `docs/original/`, `docs/refined/` and `docs/lessons-learned/`,
  plus legacy `docs/processed/`, `docs/progress/` and root `progress/`. It reads the
  packages on demand and writes no generated index into the project.
- Legacy `docs/progress/<contract-id>/` entries expose the contract ID, latest version, each
  version's task IDs, `progress.md` and explicitly linked attachments. Missing or
  unlinked attachments, filename/metadata mismatches, duplicate canonical/legacy
  identities and the same contract ID in both locations are errors; catalog and search never select one conflicting copy silently.

### 1.2. Scoped search and supported sources

- Run `<plugin-root>/scripts/search_documents.py --project-root <project-root> --query <text>` to search
  catalog metadata, Original links, Refined and legacy progress Markdown (including detailed
  Markdown under `references/`) and Lessons Learned Markdown joined with runtime metadata.
  Optional `--type`, `--category`, `--scope` and `--limit` filters narrow results.
- Catalog and search accept `--documents-root <physical-workspace-containing-docs>` while
  `--project-root` retains runtime identity. New category hierarchies and legacy layouts
  are both discovered; duplicate identities fail instead of choosing a copy.
- Search includes every versioned contract and supported text attachment. The `refined`
  type filter is an alias for the compatible `processed` metadata type; both filters
  return canonical Refined and legacy Processed records.
- Catalog and search are read-only discovery operations. They do not activate a
  Refined or Lessons Learned Document, or legacy progress record, as a Skill;
  they neither change authority nor index `docs/skills/`.
- For model-facing search/read output, use `--compact`: compact JSON with no content loss.
  The default keeps the existing indented JSON and field layout.

### 1.3. Matching and source revision

- Search defaults to the compatible `--match all` (all query substrings, case-insensitive).
  Explicit `--match any` explores partial lexical matches, prioritizing term coverage before
  frequency; it performs no translation or semantic authority inference. `--offset` pages
  through `totalCount` with `nextOffset`, without changing the existing default page size.
- Results add `documentId`, dependency SHA-256 hashes, a package `revision` and matching
  source paths/ATX section anchors. These identify exact sources for caller-side reuse;
  no persistent cache, automatic deduplication or new editable index is created.
- Use the same search CLI with `--read-path <project-relative-path>` instead of `--query`
  to read canonical Document text, or an explicitly selected `docs/skills/` entry/reference.
  `--anchor <HTML-id-or-heading-slug>` selects a section including its children;
  missing/ambiguous anchors fail instead of guessing. Fenced headings are ignored.
  The response retains complete entry guidance, source metadata and dependency hashes.
- Reuse that complete entry text and its section index for other sections already present
  at the same known revision. Do not reread the entry for each anchor. After a source change,
  missing context or uncertain freshness, read the affected sources again with revision checks.
- For several still-needed sources, use `--read-selections-file <json-file>` instead of
  `--read-path`. The file is a nonempty JSON array of objects with `path` and optional
  `anchor`/`revision`, using the same values as single reads; keep it in run storage.
  The response is one `document-read-context` bundle in input order; add `--compact` to
  share entry guidance and metadata. Do not load unrelated references merely to batch them.
  Global `--anchor`/`--revision` are invalid with this mode. Invalid selections, stale
  revisions or a package revision changing between reads fail without partial output.
- Compact single reads use `kind: document-read-context` and `layout: shared-sources-v1` only
  when smaller than compact inline JSON; otherwise the existing read object is returned.
  Batches always retain the context bundle; compact batches use the same sharing/fallback rule.
  In the shared layout, `reads` identify `documentRef`/`sourceRef`; `documents` retain metadata,
  dependencies and `entrySourceRef`. `sources` hold exact text ranges. `start`/`end` are Unicode
  code-point offsets in the original source; subtract the covering excerpt's `start` to slice
  its text. Read all entry guidance once. Overlapping
  selections share text, without dropping decisions, exceptions, hashes or unassessed sections.
- Supply the returned `--revision <hash>` when reading to reject stale sources after
  body, reference, attachment or projected status changes. Hashes are rebuilt live;
  no timestamp-only cache can hide edits. There is no atomic multi-file snapshot against
  concurrent editors. A selected section is a discovery aid: read linked mandatory rules,
  decisions and exceptions before acting. Search rank never selects execution authority.

### 1.4. Validation and historical evidence

- Reject malformed metadata, duplicate identities, links, unsupported package content
  and symlinks instead of silently omitting them from discovery. Metadata must stay
  JSON-compatible: quote YAML dates and timestamps such as `"2026-10-07"`.
- When past execution history is relevant, search it with `--type refined --category history`
  and exact-scope [lesson retrieval](lessons-learned.md#lifecycle-cli). Results are
  evidence, not current authority or active rules; recheck the current request,
  canonical Skill and authorization. On a catalog error, do not repeat the same search
  or bypass the document: report the failing path and error, and repair it only within
  the task's write scope.

<a id="request-context"></a>

## 2. Request-bound retrieval

### 2.1. Request selection contract

- Managed document-dependent requests can supply `exec.py submit/send --document-context-file <json>`;
  delegated task entries can instead carry the same `documentContext` object. Both are
  captured per request and consumed by `runs/attempt.py` before the existing provider turn.
  They are retrieval requirements, not execution approval, Skill activation or persistent session settings.
- The object accepts `query`, exact `scope`, explicit `allowPartial`/`discoverScopes`/`includeHistory` booleans,
  and `required`/`selections` lists of `{path, anchor?, revision?}` canonical sources.
  Supply mandatory rules, Human decisions and exceptions in `required` independently of
  query ranking. A conflicting task/CLI object is rejected. With no object, normal requests
  perform no extra Document reads. Empty objects and unsafe paths are rejected.

### 2.2. Complete retrieval and history

- Retrieval consumes the complete `all` result set once, tries `any` only on a miss with `allowPartial`,
  and explores other scopes only on a miss with `discoverScopes`. Cross-scope results retain
  scope/status and `discoveryOnly`; discovery never grants applicability or authority.
  Narrow matching sections retain complete entry text. Explicit mandatory/exception links
  are followed recursively; ordinary references stay unloaded and listed as unassessed.
  The cue recognizer is conservative, not a semantic completeness proof. Unselected sections,
  external links and unclear dependencies stay visible; resolve required gaps by canonical
  reading before acting. Missing required sources and stale explicit revisions block preparation.
- Refined `history` search hits stay visible as historical candidates, without automatically
  loading their bodies. Set `includeHistory: true` when past evidence is relevant; explicit
  `required`/`selections` and mandatory dependencies remain readable regardless of this flag.
  Historical reads retain that label and grant no automatic current-rule authority.
  Imperatives inside historical content do not activate dependency reads; their links
  remain visible for explicit lookup. Current mandatory references keep their existing behaviour.

### 2.3. Shared snapshot and delivery evidence

- One request reuses its validated catalog across fallback queries and selected reads.
  Each selected package's metadata and dependency hashes are reread live, so reuse cannot
  silently accept a stale explicit revision. A later request builds a new catalog.
- Model delivery shares complete source text and package metadata through explicit
  `sources`/`documents` references. Selected character ranges, entry guidance, provenance,
  decisions, dependency hashes and unresolved gaps remain present. Default CLI reads retain
  their inline format; `--compact` opts into source sharing. Small bundles keep the inline
  layout when sharing would increase bytes. Model delivery uses compact JSON in either layout.
- Run status exposes `documentContext` and per-attempt `documentContextAttempts`: search
  misses/failures, requeries, repeated path reads, sections, revisions, hashes, read latencies,
  snapshot file bytes, catalog build/reuse counts and delivered JSON bytes. Delivery adds
  `contextLayout`, `unsharedContextBytes` and `savedContextBytes` for actual serialization savings.
  Snapshot bytes exclude catalog parsing I/O;
  `catalogReadBytes`, model input tokens, token estimates and document-cache counters are
  unavailable (`null`). `modelUsageJoin` links the same run/attempt to existing `usageAttempts`
  and `tokenUsage`; reported provider usage is not attributed to individual Document tokens.
  No extra model call, persistent cache or copied editable source is created.
