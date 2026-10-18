---
name: tool
description: Find the Agent Factory script and rules for a plugin operation. Use for plugin tool selection, not general-purpose CLIs.
metadata:
  specification-id: tool
---

# Agent Factory Tool

- `<plugin-root>` is the installed Agent Factory plugin directory that contains `skills/`,
  `runtime/` and `scripts/`; it is two levels above this `SKILL.md`.
- This catalog selects a function, not a role. Captured role and Human authority remain
  binding; the owning function's method, precondition and failure rules still apply.
- Run every tool as `python3 <plugin-root>/scripts/<script> ...`.
- Select one script, then read its generated usage/subcommand and the matching Rules
  reference. Reuse supplied guidance; other rows, usage files and role prompts are not
  additional required reads. Inspect role sources only when they are assigned task data.
- `exec.py` usage is a command index; read only the selected command's linked options page.

<a id="catalog"></a>

## 1. Plugin tools

| Script / usage | Operation | Rules |
|---|---|---|
| [`archify.py`](references/usage/archify.md) | Pinned Archify JSON validation, HTML delivery and external file opening | [Archify diagrams](../convention/references/archify.md) |
| [`exec.py`](references/usage/exec.md) | One managed run | [Agent](../agent/SKILL.md) |
| [`coordination.py`](references/usage/coordination.md) | Append Main-owned contract control/decision records | [Coordination records](../agent/references/role-exceptions.md#coordination-records) |
| [`commit.py`](references/usage/commit.md) | Main-owned receipt-bound ordinary local commit | [Commit boundary](../agent/references/role-exceptions.md#ordinary-local-commit) |
| [`loop.py`](references/usage/loop.md) | Announced Work/Verification loop | [Agent](../agent/SKILL.md) |
| [`conductor.py`](references/usage/conductor.md) | Durable chat execution routing, observation and report delivery | [Agent](../agent/SKILL.md) |
| [`conductor_queue.py`](references/usage/conductor_queue.md) | Multi-conductor chat queue: durable ingress, fenced turns, delivery recovery and UI feed | [Agent](../agent/SKILL.md) |
| [`domains.py`](references/usage/domains.md) | Shared project domain list and worker memberships (Human-protected) | [Task allocation](../agent/references/task-allocation.md#project-domains) |
| [`evidence.py`](references/usage/evidence.md) | Screen capture with browser log, baseline-compared checks, shared environment holds | [Verification environment](../convention/references/verification-environment.md) |
| [`operation_records.py`](references/usage/operation_records.md) | Read-only Task/Session/Decision/Observation lookup and record search | [Agent](../agent/SKILL.md) |
| [`lessons.py`](references/usage/lessons.md) | Lessons and published rules | [Lessons](../document/references/lessons-learned.md#lifecycle-cli) |
| [`migrate_runtime_lessons.py`](references/usage/migrate_runtime_lessons.md) | Merge legacy runtime captures by signature | [Lessons](../document/references/lessons-learned.md#runtime-capture) |
| [`sync_documents.py`](references/usage/sync_documents.md) | On-demand host synchronization | [Host sync](../document/references/host-sync.md#continuous-codex-synchronization) |
| [`export_documents.py`](references/usage/export_documents.md) | One-time host export | [Export](../document/references/host-sync.md#explicit-codex-export) |
| [`catalog_documents.py`](references/usage/catalog_documents.md) | Live Document catalog | [Catalog](../document/references/catalog-search.md) |
| [`search_documents.py`](references/usage/search_documents.md) | Search that catalog | [Search](../document/references/catalog-search.md) |
| [`migrate_document_paths.py`](references/usage/migrate_document_paths.md) | Document layout migration and contract-listed moves | [Migration](../document/references/migration.md) |
