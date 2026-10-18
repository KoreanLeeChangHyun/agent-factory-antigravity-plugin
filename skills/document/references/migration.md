# Document migration

<a id="document-layout-migration"></a>

## 1. Document layout migration

### 1.1. Roots and classification

- Run `python3 <plugin-root>/scripts/migrate_document_paths.py --project-root <original-project>
  --documents-root <physical-workspace-containing-docs> --storage-layout` for a read-only
  dry-run. Inspect `moves`, `conflicts`, `unclassified`, `excluded` and `languages`.
- A physical workspace contains `docs/`; for a docs repository worktree at
  `<worktree-workspace>/docs`, pass `<worktree-workspace>` as `--documents-root`.
  Runtime identity remains the original registered project, not that temporary worktree.
- Select lesson body language explicitly with `--language <tag>` when it differs from
  legacy record language. The source language and quoted original text remain preserved;
  this does not translate historical prose or change Refined package languages. Without
  this option, document languages are retained. Dry-run separates source/body language counts.
- For ambiguous Refined packages, inspect the body and supply `--classifications <json>`
  mapping project-relative source package paths to `analysis`, `research`, `interview`,
  `comparison` or `history`. Classification changes metadata only, preserves prior category
  evidence and never rewrites historical content into current rules.

### 1.2. Scope, authority and backups

- Preserve pre-existing dirty/untracked content with repeated `--exclude-path <relative-path>`.
  Excluding a member preserves its whole moving package. Review incoming links in excluded
  content separately; migration never changes those files.
- Only explicit migration authorization permits apply and source retirement. Add
  `--apply --backup-dir <authorized-outside-workspace-backup>` after resolving conflicts
  and unclassified packages. The backup holds exact source/target bytes, hashes and mapping.
- Backups may use an existing run's storage below its `agents/<agent>/runs/<run>/`
  directory, or another authorized location outside the physical document workspace.
  Runtime control and lesson metadata directories are not backup destinations.

### 1.3. Verification and resumable apply

- Verify all output hashes and complete lesson history round trips before removing old files.
  Attachments and empty package directories are preserved. Local Markdown links in entries,
  references and incoming project documents follow moved targets.
- Retry with the same backup after a partial failure. The manifest permits only its original
  and expected bytes; changed sources, independently edited targets, duplicate identities
  and existing unowned destinations require reconciliation, never silent replacement.
- After apply, run catalog and scoped search with the same two roots, inspect language,
  body meaning, links and history, and retain the backup as restoration evidence.
  Refined never needs host synchronization. Synchronize only affected Specification sources
  through the existing host contract; this migration does not authorize host overwrite.

### 1.4. Legacy operations and Scribe guards

- Without `--storage-layout`, the existing contract-listed `--operations` preview/backup/apply
  interface remains available; `--documents-root` selects its physical file workspace too.
  No separate README catalog, database or document system is created.
- Scribe uses the guard's own `<plugin-root>/scripts/migrate_document_paths.py` for authorized
  contract-listed moves. Pass literal captured `--project-root` and `--documents-root`, plus
  `--operations <CSV>` inside `docs/` or the current run. Each selected source and destination
  must remain inside the captured document write root; symlinks and overlapping endpoints fail.
- Preview returns source and expected destination SHA-256 hashes, including intentional link
  adjustments. Run `--backup`, then `--apply` with the same
  `--backup-dir <current-run>/document-backups/<name>`. Apply requires the completed matching
  manifest and verified bytes. Re-run preview with that backup to check completed moves.
  Backup data cannot replace run control records, use another run or escape through symlinks.
- Scribe's CLI checks its captured scope again at execution; a hook decision does not bind
  mutable CSV contents. Arbitrary shell/code execution and `--storage-layout` remain forbidden
  for Scribe. These capabilities grant no new migration, directory creation or draft acceptance
  authority. Storage-layout changes that update runtime lesson metadata use an authorized Work.
