# Provider and model prompt guidance

<a id="applicability"></a>

## 1. Applicability

- Apply the [shared writing and context rules](prompting.md). The common rules are an
  Agent Factory synthesis; supplier recommendations do not imply identical prompt layouts.
- Identify the active model/version, API or host, and deployment before using a row below.
  Recheck the linked official guidance when these change. Sources reviewed: 2026-10-17.
- Keep mandatory instructions in their privileged role. Within task data, long documents
  can precede the task-specific question without changing instruction priority.
- Use enough relevant context and representative examples to meet the task. Anthropic's
  [context engineering guide](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  supports targeted retrieval and concise tool interfaces; brevity alone is not the goal.

<a id="provider-differences"></a>

## 2. Provider differences

| Provider | Prompt and conversation guidance | Cache and interface conditions |
| --- | --- | --- |
| OpenAI | Use clear roles, task/data boundaries and output requirements. Follow the chosen model's [prompt guide](https://developers.openai.com/api/docs/guides/prompt-engineering) and [reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning-best-practices); do not copy one model family's reasoning recipe to another. | [Caching](https://developers.openai.com/api/docs/guides/prompt-caching) benefits from stable prefixes. Preserve native schemas and conversation state; check model/endpoint eligibility and actual usage rather than assuming savings. |
| Anthropic / Claude | [Prompting guidance](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) recommends explicit goals, representative examples and clear document/source boundaries. For long-document tasks, put the data before the task-specific query; retain required system rules. | [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) uses `cache_control` for automatic caching or block breakpoints. The prefix hierarchy is tools → system → messages; changing earlier content can invalidate later cache entries. Check model/host support and lifetime. |
| Google / Gemini | [Prompt design guidance](https://ai.google.dev/gemini-api/docs/prompting-strategies) favors few-shot examples; tune their count and consistent format against the task. Keep critical system instructions; for long context, place the task-specific question after the evidence. Do not remove useful examples merely to shorten input. | [Implicit caching](https://ai.google.dev/gemini-api/docs/caching) reuses common prefixes. [Explicit cache objects](https://ai.google.dev/gemini-api/docs/generate-content/caching) are conditional on the model and API; do not assume that Interactions and GenerateContent expose the same controls. |
| Meta / Llama | [Prompt engineering guidance](https://dev.meta.ai/llama/docs/how-to-guides/prompting) covers clear constraints, useful examples and removing unnecessary output preambles. Use the selected model's format: [Llama 3.3](https://github.com/meta-llama/llama-models/blob/main/models/llama3_3/prompt_format.md) and [Llama 4](https://github.com/meta-llama/llama-models/blob/main/models/llama4/prompt_format.md) differ in role/control tokens. Preserve message boundaries, turn endings and tool syntax. | For direct inference, use the matching tokenizer/chat template; for hosted inference, follow the host's interface. Do not mix generations or add raw control tokens to an API that already formats messages. Cache behavior depends on the serving deployment, not the model weights alone. |
| xAI / Grok | For the supported reasoning API, [best practices](https://docs.x.ai/developers/model-capabilities/text/best-practices) preserve returned encrypted reasoning and tool-call items unchanged across turns. Native state preservation is distinct from asking the model to expose its reasoning as prose. | [Automatic prompt caching](https://docs.x.ai/developers/advanced-api-usage/prompt-caching) matches prefixes. Stable content and a per-conversation `prompt_cache_key` help reuse; a key does not guarantee a hit. Avoid editing earlier items merely for prompt brevity. |

<a id="validation-and-boundaries"></a>

## 3. Validation and boundaries

- Treat ordering, example count, reasoning controls and cache settings as conditional
  choices, not universal constants. Preserve capability, source fidelity and authority
  before comparing size, latency or cost.
- Check representative long-document, structured-output and multi-turn/tool cases on
  the actual model/API. Count tokens with its tokenizer or supported counting interface;
  inspect native usage/cache fields rather than transferring another provider's estimates.
- Meta's multi-sample self-consistency technique trades more computation for possible
  quality gains. It is not a token-saving default; evaluate its added usage only within
  the task's authorized cost and quality scope.
- This reference grants no model switch, paid call, API migration or new retention policy.
  Apply cache controls or native compaction only where the runtime supports them and
  the task authorizes them; preserve decisions, pending work and source access.
