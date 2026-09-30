# Agent Factory for Antigravity

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory is an Antigravity CLI (`agy`) plugin for Human-directed software delivery. It
provides four Skills: `agent` for managed Work and Verification execution, `convention` for
shared project rules, `document` for authoring and synchronizing project documents, and
`tool`, a catalog of the plugin scripts and the Skill that owns each one.

Version: `1.0.24`

## Install

```sh
agy plugin install https://github.com/KoreanLeeChangHyun/agent-factory-antigravity-plugin
```

The runtime uses the Antigravity CLI and its existing Google AI subscription login. No API
key, MCP server or account connection is required. Python 3.10+ is required.

## VS Code extension

The Agent Factory VS Code extension is optional. When the `agy` CLI is available, it
installs or updates this plugin at the extension's semantic base version.

## Document synchronization

Project specification documents in `docs/skills/` are synchronized to `.agents/skills/`,
`.codex/skills/` and `.claude/skills/` by the Document Skill's `sync_documents.py`, making
them available as project Skills. Synchronized output must not be edited directly;
independent edits are reported as conflicts.

## License

MIT License. See [LICENSE](LICENSE).
