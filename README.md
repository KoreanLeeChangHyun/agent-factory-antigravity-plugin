# Agent Factory for Antigravity

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory is an Antigravity CLI (`agy`) plugin for Human-directed software delivery. It
provides four Skills: `agent` for managed Work and Verification execution, `convention` for
shared project rules, `document` for authoring and synchronizing project documents, and
`tool`, a catalog of the plugin scripts and the Skill that owns each one.

Version: `1.0.31`

## How it works

![You talk only to the Conductor. It writes a work request; performers carry it out and write a work report; the Conductor compares the report with the Done criteria before it answers you. A Verifier checks the work only when you ask.](https://raw.githubusercontent.com/KoreanLeeChangHyun/agent-factory-vscode-extension/main/static/images/readme-conductor.png)

- The **Conductor** (Main) converses, plans and routes. By default it delegates every change and
  research task to a performer: **Expert** (`work`), **Worker** (`workLight`), **Explorer**
  (`explore`) or **Scribe** (`scribe`). In direct mode it works itself.
- A **work request** (goal, scope, Done criteria) is the only handoff to a performer; the **work
  report** returns the result, changed paths and the performer's own checks. The Conductor compares
  each report with its Done criteria before reporting, and a **Verifier** checks the work when you ask.
- Every performer belongs to a named domain. Agents run in the CLI their model selects (Antigravity, Codex or
  Claude Code), with its existing login.

## Core features

![Documents, interviews and lessons: sources become research, accepted research becomes Specification, and Specification is synchronized into project Skills that agents load. Interviews record decisions; agents record lessons and contracts; supported lessons are consolidated into rules.](https://raw.githubusercontent.com/KoreanLeeChangHyun/agent-factory-vscode-extension/main/static/images/readme-knowledge.png)

- **Document system:** Original, Refined, Specification, Progress and Lessons Learned, with one
  editable source per document. Accepted Specifications become project Skills.
- **Contracts → Work–Verification loop:** a versioned contract of tasks, Done criteria and order,
  carried out by Work and checked by Verification until it passes.
- **Interviews:** one material decision at a time, with options, trade-offs and a recommendation.
- **Lessons learned:** errors and judgment differences recorded with causes and outcomes, retrieved
  before related work and consolidated into rules only when you ask.

## Install

```sh
agy plugin install https://github.com/KoreanLeeChangHyun/agent-factory-antigravity-plugin
```

The runtime uses the Antigravity CLI and its existing Google AI subscription login. No API
key, MCP server or account connection is required. Python 3.10+ is required.

## VS Code extension

The Agent Factory VS Code extension is optional. When the `agy` CLI is available, it
installs or updates this plugin at the extension's semantic base version, and adds the
Conductor chat and the Control Center.

![The Agent Factory VS Code extension: the Control Center shows performers by domain and the work report of one execution.](https://raw.githubusercontent.com/KoreanLeeChangHyun/agent-factory-vscode-extension/main/static/images/readme-control-center.png)

## Document synchronization

Project specification documents in `docs/skills/` are synchronized to `.agents/skills/`,
`.codex/skills/` and `.claude/skills/` by the Document Skill's `sync_documents.py`, making
them available as project Skills. Synchronized output must not be edited directly;
independent edits are reported as conflicts.

## License

MIT License. See [LICENSE](LICENSE).

## Source

This repository is generated. Do not edit it directly; changes are made in
[https://github.com/KoreanLeeChangHyun/agent-factory-plugin-source](https://github.com/KoreanLeeChangHyun/agent-factory-plugin-source) and published with `distribution/port.py`.
