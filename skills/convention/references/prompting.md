# Document and prompt writing

<a id="concise-wording"></a>

## 1. Document and prompt wording

- Write technical documents and AI-facing prompts concisely in the selected language.
  Human-facing chat retains the [required register](communication.md#required-register).
- Korean: end document and prompt items in nominal form (`삭제 금지`, `기본값: 3`), not
  `입니다`/`아닙니다`/`~해 주세요` sentences. Human-facing chat keeps its register.
  English and other languages: use natural, direct wording. Do not translate for token savings
  or duplicate content in two languages unless the request or governing format requires both.
- Write content as short bulleted or numbered items, one point each, not prose paragraphs.
- Preserve actor, action, obligation, permission, negation, scope, conditions, exceptions and
  source identifiers. Distinguish inability, prohibition, missing evidence and incomplete work.
  Keep requirements explicit; avoid cryptic abbreviations that hide a rule.
- Preserve quotations, code and exact sources under [content fidelity](communication.md#content-fidelity).
- Remove repeated introductions, restatements and examples that add no decision or format guidance.
  Skill descriptions identify capability and trigger; bodies route to task-specific detail.
  Do not replace necessary context with unexplained shorthand.
- Compare the same content and coverage before/after. Name the tokenizer and version used;
  an alternate tokenizer is an estimate for the target model. Claim target-model token savings
  only with its tokenizer. Character/byte reduction alone is not token reduction.

| Verbose wording | Concise equivalent |
| --- | --- |
| 기본값은 3입니다. | 기본값: 3 |
| 승인 전 삭제를 금지합니다. | 승인 전 삭제 금지 |
| 필수 항목이 아닙니다. | 필수 항목 아님 |
| 검증 결과는 아직 확인되지 않았습니다. | 검증 결과 미확인 |
| You must obtain approval before deleting files. | Obtain approval before deleting files. |

<a id="section-table-order"></a>

### 1.1. Section visual order

- Within each content section/subsection, place explanations and lists before tables,
  figures, images, shapes and diagrams; group visuals before the next heading or EOF.
- Preserve their headed scope, captions, legends, asset links, order, data, identifiers
  and list-item associations. Add a meaningful subsection when needed to retain the subject.
- Include rendered and text diagrams. Move diagram sources intact; preserve literal
  quotations and source/code examples exactly.

<a id="section-scope"></a>

### 1.2. Section topic and purpose

- Give each section one topic and reader purpose matching its heading. Separate independent
  decisions, actions or responsibilities into meaningful sections/subsections.
- Keep essential guidance at the entry; link detail needing separate reading or maintenance.
  Each rule has one canonical owner. Link instead of copying; preserve conditions, exceptions,
  sources and unresolved choices.
- Divide by meaning and ownership, without arbitrary length/item limits, empty headings or
  fragments that require reconstructing an instruction. Apply [visual order](#section-table-order).

<a id="targeted-revision"></a>

### 1.3. Targeted revision and delivery

- Edit the smallest coherent clause; preserve unrelated text, anchors and identifiers.
  Check adjacent clauses and affected links. Rewrite the whole document only when needed
  for the requested content or structure.
- After editing a file, report changes, its link and relevant checks. Deliver the full body
  once only when requested or required by the output contract.

<a id="prompt-composition"></a>

## 2. Prompt composition and context

### 2.1. Rule ownership and message roles

- Give each outcome, constraint, authority rule and output contract one owner. Remove
  duplicate copies while preserving task cues, conditions and evidence.
- Separate stable instructions from variable requests/IDs within existing message roles.
  Preserve priority and controls; never move privileged rules into untrusted input for cache
  savings. Ordering and cache controls depend on the model/API.
- Distinguish instructions, literal requests and evidence with headings or collision-safe
  delimiters. Specify the output form using the existing schema instead of duplicate prose;
  omit preambles the task does not need.

### 2.2. Routing, examples and context

- Use precise Skill triggers and concise entry routers. Find Documents by name/description/path
  or scoped search; use returned anchors/revisions. Read entry guidance, relevant sections and
  mandatory dependencies, decisions and exceptions; links are not a reading checklist.
- Reuse current supplied text. After a source change or revision mismatch, reread affected
  sections/dependencies without omitting required context or reusing stale authority.
- Keep useful task/model-specific format and edge-case examples. Avoid redundant examples,
  universal zero-shot/few-shot quotas and ritual demands for step-by-step reasoning;
  request results and necessary evidence.
- Separate current rules from [history](../../document/references/specification.md#current-and-history).
  Retrieve relevant evidence with scope/revision, preserving sources, exceptions and unresolved gaps.
- Optimize for sufficient relevant context, using targeted queries and retrievable references.
  Do not sacrifice mandatory evidence or unresolved state for a shorter prompt.

### 2.3. Evaluation and provider sources

- Evaluate representative cases on the target model/API for authority, fidelity, ambiguity
  and output validity before accepting an optimization. Record the version; measure tokens,
  latency, cost and cache reuse separately. Bytes and software tests do not establish model quality
  or cache savings.
- Read `prompting-providers.md` ([provider and model guidance](prompting-providers.md))
  only for OpenAI, Anthropic, Google, Meta or xAI adaptation; use the applicable row.
- Sources: [prompt structure](https://developers.openai.com/api/docs/guides/prompt-engineering),
  [cache-friendly prefixes](https://developers.openai.com/api/docs/guides/prompt-caching),
  [Skill routing](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra),
  [reasoning prompts](https://developers.openai.com/api/docs/guides/reasoning-best-practices),
  [evaluation](https://developers.openai.com/api/docs/guides/evaluation-best-practices) (accessed 2026-10-17).
