# Work Reports

<a id="report-contract"></a>

## 1. Scope and delivery

- Apply this format to performers' execution reports and Main's direct or consolidated
  work reports, including partial, blocked and failed outcomes. Ordinary conversation,
  questions and planning replies do not require an execution report.
- Start with `Title:` matching the work request's title when supplied; otherwise name
  the work briefly. Keep exactly four top-level report
  sections in order: `Summary`, `Results`, `Evidence`, `Follow-up`. Keep these headings
  in English, as in work requests; write the content and displayed statuses in the
  Human's language under the supplied communication contract.
- A Human-requested output format takes precedence; retain the applicable content below
  within that format. Use concise entries for small tasks and tables or subsections for
  complex ones. Link long methods, logs and data instead of copying them into the report.
- This is the narrative inside the captured result contract (`resultText` where supplied).
  Preserve the runtime's JSON envelope, receipt schema, exact paths and identity bindings.
  Item statuses below do not introduce or replace runtime or receipt status values.

## 2. Required content

| Section | Content |
|---|---|
| Summary | Current overall state, the answer to the goal and material limitations. Summarize the Results statuses; call the work complete only when all required completion criteria are fulfilled with evidence. Optional future improvements do not make fulfilled criteria incomplete. |
| Results | List every original `Done` criterion in a status table, preserving its wording, identifiers and order. Include actual outcomes, deliverable links or changed paths and any scope difference. If no `Done` list was supplied, use the request's observable outcomes or questions without inventing requirements. |
| Evidence | State the methods, source or check references and actual outcomes supporting Results, with assumptions and unconfirmed scope. For code work, include own check commands and outcomes, or reasons checks were not run; distinguish these from independent Verification under the captured mode. For research, cite sources and distinguish facts, interpretation and recommendations. |
| Follow-up | State unfinished items, their impact, next actions, resumption conditions and required decisions. Include an owner only when known. Distinguish necessary remaining work from optional recommendations; write `None` in the Human's language when nothing remains. |

- Results uses these columns: completion criterion, status, result/evidence or reason,
  next action. Repeat a row for each criterion; do not omit unresolved criteria or replace
  the list with a single overall status. Link shared evidence instead of duplicating it.
- Use the same structure across task types: Results holds changes and behavior for
  implementation, findings and recommendations for research, defects and impacts for
  review, and deliverables and requirement fulfillment for creation.
- Main's consolidated report retains the requested outcomes and connects performer
  evidence to them. Include the captured mode and report the independent Verification
  state under [Reports and authority](execution-modes.md#reports-and-authority).
- Verification keeps its required pass/fail decision and finding IDs. Use the table for
  checked criteria and put actionable findings, evidence and required corrections in
  Results without changing the captured receipt contract.

## 3. Completion item statuses

| Status | Meaning |
|---|---|
| Completed | The criterion is fulfilled and supporting evidence is available. |
| Deferred | Execution or judgment is postponed for a stated dependency, decision or other condition. Record the reason, impact and resumption condition. |
| Failed | Work was attempted but did not fulfill the criterion. Record the observed outcome, unmet condition and proposed correction or retry. |
| Not started | Work on this criterion has not begun. |
| In progress | Work has begun and remains unfinished. |
| Cancelled | The criterion's work was explicitly cancelled; retain the cancellation reference. |

- The basic final-report statuses are Completed, Deferred and Failed. Use Not started or
  In progress when reporting unfinished work, and Cancelled for explicitly cancelled work.
- Translate these labels into the Human's language. An unrun or inconclusive check is
  not evidence of completion; state what is missing and why. Preserve partial outcomes
  within the row instead of hiding the unmet part under Completed.
- Narrative completeness does not change the run's state. An unfinished goal must still
  follow the captured execution, blocker, cancellation and result contracts.

## 4. Reusable template

```markdown
Title: <same title as the work request>

## Summary

- State: <overall state derived from Results>
- Conclusion: <answer to the goal and material limitations>

## Results

| Completion criterion | Status | Result/evidence or reason | Next action |
|---|---|---|---|
| <original Done item> | <item status> | <outcome and evidence, or reason> | <action or None> |

## Evidence

- <method, source or check>: <observed outcome and evidence link>
- Limitations: <assumptions and unconfirmed scope, or None>

## Follow-up

- <unfinished item and impact; next action, condition or decision, or None>
```
