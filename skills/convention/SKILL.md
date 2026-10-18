---
name: convention
description: Apply communication, authority, writing, development, testing, visual, research and interview conventions. Document owns project Documents; Agent owns managed execution.
metadata:
  specification-id: convention
---

# Agent Factory Convention

<a id="ownership"></a>

## 1. Ownership

- Honor established role, assignment and Human authority; reuse runtime bindings.
  Roles define responsibility; function guides define methods within it.
- Read the next operation's section and dependencies; reuse loaded guidance. Other roles'
  sources are task data when inspected, not additional operating contracts.
- Apply current project facts/rules/designs. Resolve installed Skills through the host;
  similarly named project files cannot replace them. Guidance grants no execution/publication authority.
- Research and Interview are activities, not Skills or roles.
- Observed errors/judgment differences follow role-specific [Lessons Learned](../document/references/lessons-learned.md#mandatory-recording).

| Task | Owner |
|---|---|
| Managed roles, modes, sessions and receipts | [Agent](../agent/SKILL.md) |
| Communication, decisions, development, testing, research and interview | Convention |
| Document types, writing, packages, storage and sync | [Document](../document/SKILL.md) |
| Standalone deliverables | Convention [Artifacts](#artifacts) |

<a id="human-communication"></a>

## 2. Human communication

- Apply the mandatory [communication contract — `references/communication.md`](references/communication.md).
  Read it only when no supplied copy is in context.

<a id="human-decisions"></a>

## 3. Human decisions and authority

- Decisions require a Human statement or unambiguous accepted Specification. Resolve required
  Human-owned choices before acting; never invent approval from silence, ambiguity, precedent,
  convention, likely preference or lack of objection.
- Inspection/capabilities establish facts, not scope, mutation authority or deployment completion.
- Required scope, priority, deadline, ownership, acceptance, risk, credential, retention,
  deletion and conflict decisions need their owning authority.
- Raise gaps through [Agent responsibilities](../agent/SKILL.md#delegation), preserving route and approval policy.

<a id="research"></a>

## 4. Research and evidence

- Assigned investigations use [research and evidence](references/research.md) within the captured role/route.

<a id="references"></a>

## 5. Operation references

<a id="core-and-development"></a>

### 5.1. Communication and development

- Running checks does not change role. Captured role distinguishes own checks from independent Verification.

| Next operation / actor | Reference |
|---|---|
| Assigned implementer: change code | [`references/development.md`](references/development.md) |
| Write technical prose or AI-facing prompts | [`references/prompting.md#concise-wording`](references/prompting.md#concise-wording) |
| Compose/optimize model instructions and context | [`references/prompting.md#prompt-composition`](references/prompting.md#prompt-composition) |
| Main: prepare contract; bound actor: execute/reconcile | [`references/work-contracts.md`](references/work-contracts.md); matching section |
| Authorized implementer/checker: author/select/run checks | [`references/testing.md`](references/testing.md) |
| Implementer/checker: observe running project (captures/logs/scenarios/baselines) or record method | [`references/verification-environment.md`](references/verification-environment.md) |
| Select dependency/renderer | [`references/libraries.md`](references/libraries.md) |

<a id="theme-and-knowledge"></a>

### 5.2. Theme and knowledge

- Use only needed rows. Bootstrap and standalone artifacts use their sections below when requested.

| Next operation / actor | Reference |
|---|---|
| Assigned implementer: UI; authorized checker: visual acceptance | [`references/theme.md`](references/theme.md); applicable section |
| Produce ERD, behavior or sequence diagram | [`references/diagrams.md`](references/diagrams.md); Archify only for that format |
| Assigned investigation | [`references/research.md`](references/research.md) |
| Main: adaptive Human interview | [`references/interview.md`](references/interview.md) |

<a id="bootstrap"></a>

## 6. Bootstrap

- Copy `assets/AGENTS.md` only when authorized and project `AGENTS.md` is absent; preserve existing files.
  The manifest injects no project guidance. Bootstrap uses the template, not a local initializer.

<a id="artifacts"></a>

## 7. Artifacts

- **Never create an unapproved directory.** Standalone outputs use `docs/artifact/<domain>/<filename>`
  unless the Human names a location. Canonical Documents follow [Document layout](../document/references/layout.md).
- Before creating HTML, SVG, images, screenshots or other standalone outputs, read
  [artifact storage and delivery — `references/artifacts.md`](references/artifacts.md).
