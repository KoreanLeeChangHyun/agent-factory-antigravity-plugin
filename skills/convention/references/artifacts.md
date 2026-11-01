# Artifacts

## 1. Storage and delivery

- **Never create an unapproved project directory**, including scratch, output, backup,
  test or tool directories. Standalone deliverables use `docs/artifact/`; canonical
  Documents follow the [Document layout](../../document/references/layout.md).
- The artifact root has exactly ten domain directories from the table below and no
  nested directories. The only root control file is `index.json`. No `SKILL.md`
  wrapper, Document metadata or Skill synchronization is required.
- Write `docs/artifact/<domain>/<filename>`. Put topic, date and release version in
  filenames, for example `release/product__1.2.3.zip`; never create task, date, version
  or format subdirectories. A new domain needs explicit Human agreement.
- For a multi-file deliverable, stage in run storage or system temp and deliver a ZIP
  or TAR in its domain. Keep original relative paths inside the archive. Extract for
  use in run storage or system temp, never into the artifact tree. A standalone HTML
  file can be delivered directly when its dependencies are embedded.
- Honor a Human-named output location without silently changing the fixed layout.
  Preserve existing outputs and use a unique filename instead of overwriting them.
- Keep application source in its owning source tree, files a Document links (diagrams, datasets,
  images) in their artifact domain, and live runtime homes, locks, caches and disposable raw logs
  in run storage or system temp. Remove disposable scratch after successful delivery.
- Artifacts are not automatically committed, published or synchronized to host Skills.
  Preserve the task's authority. Verify the format and provide a clickable file link;
  distinguish saved output from rendered or visually inspected output.

<a id="git"></a>

## 2. Git handling of `docs/`

- Commit canonical Documents (`skills/`, `refined/`), Original source records and artifact
  deliverables. Keep `lessons-learned/` local; only adopted rules move into committed Documents.
  In `evidence`, commit fixed-name approved material such as comparison baselines; per-run
  bundles named `<topic>__<13-digit epoch ms>-<id>.zip` stay local and are pruned to the
  newest five per topic plus the last seven days by their producer.
- `exec.py docs-git status` reports whether the project and `docs/` are repositories, the
  recorded mode, a suggested mode and tracked files the rules now ignore. `apply --mode
  project|separate|local` records the Human's choice, creates missing artifact domains and
  writes only Agent Factory's marked block in `docs/.gitignore` (plus `/docs/` in the root
  `.gitignore` for `local`). Lines outside the block stay untouched.
- In `project` mode, `status` also reports `conflict`: a rule outside the block that still
  ignores all of `docs/`. `unignore` removes that exact line only from a project `.gitignore`
  after the Human agrees; global and `.git/info/exclude` rules are reported, never edited.
- The mode, creating a repository and untracking reported files are Human choices. Never run
  `git init`, untrack, commit or change the index from these commands or a recording operation.

## 3. Domain selection

First exclude canonical Documents, live source and runtime storage. An explicit
release bundle belongs in `release`; a version number alone does not make a release.
Selected observation/check material belongs in `evidence`. Otherwise classify by the
principal delivered representation, keeping mixed-format bundles intact. Classification
implies no approval, correctness, publication or Verification pass.

| Domain | Delivered content |
|---|---|
| `output` | Exported reports, PDFs, slides and posters; editable canonical Documents stay with their owner. |
| `media` | Images, icons, illustrations, fonts, audio, video and animation assets. |
| `diagram` | Editable diagram originals, including Archify JSON, architecture, sequence and ERD sources; Documents reference this single source. Image/PDF/HTML exports use their representation's domain. |
| `data` | Reusable datasets, spreadsheets, database and GIS exports. |
| `model` | CAD, 3D, simulation and machine-learning models or weights. |
| `software` | Standalone tools, scripts, notebooks, workflows and configuration bundles; not live application source. |
| `interactive` | HTML explanations, dashboards, prototypes, demos and games. |
| `evidence` | Selected screenshots, measurements, test logs and observation records. |
| `release` | Versioned release packages, installers, checksums, signatures and retained distribution snapshots. |
| `other` | A real deliverable outside the above domains; record its type and classification reason in the index. |

## 4. Reorganization and checks

- Inventory existing files and incoming links before moving them. Preserve provenance,
  bytes and archive member paths; verify every file's size and SHA-256 before removing
  its old path. Retain originals in run storage, check collisions and concurrent writes.
- Record old-path → archive/member mappings and hashes in `index.json`. Retain historical
  quoted paths as evidence; update live navigation and generators. If a linked image
  needs direct viewing, retain a byte-identical flat export with its source relation.
- Do not deduplicate historical observations or release versions by matching hashes.
  Do not execute archived code to classify it, or follow symlinks into runtime/dependencies.
- Producers must validate the fixed domain and flat destination before writing. Repository
  checks must reject additional/nested directories and symlinks, including empty ones.
  These checks detect drift; they are not an operating-system ban on arbitrary writes.
