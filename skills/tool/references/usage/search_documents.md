# `search_documents.py` usage

Generated from argparse by `distribution/tool_usage.py`; do not edit by hand.
Rules for when and why to run it stay in the owning Skill listed in [SKILL.md](../../SKILL.md).

Required: `--project-root PROJECT_ROOT`
One of: `--query` | `--read-path` | `--read-selections-file`
- `--query QUERY`
- `--read-path READ_PATH`: Canonical project-relative Document or docs/skills text path
- `--read-selections-file READ_SELECTIONS_FILE`: JSON array of canonical path, optional anchor/revision objects; one complete read bundle
- `--anchor ANCHOR`: Read one ATX section by explicit HTML ID or heading slug; retains complete entry guidance
- `--revision REVISION`: Require a matching package revision when reading; stale input fails closed
- `--match {all,any}`: all preserves legacy AND search; any explicitly explores partial lexical matches
- `--offset OFFSET`: Result page offset; totalCount and nextOffset expose all matches
- `--type {original,processed,progress,lessons-learned,refined}`
- `--category CATEGORY`
- `--limit LIMIT`
- `--scope SCOPE`
- `--documents-root DOCUMENTS_ROOT`: Physical workspace containing docs; runtime identity stays --project-root
- `--compact`: Compact JSON; reads may use shared-sources-v1, retaining complete entry guidance and metadata
