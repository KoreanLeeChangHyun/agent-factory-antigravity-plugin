# Runtime diagnostics

<a id="diagnostic-trace"></a>

## 6. Diagnostic trace

- New runs expose `tracePath`, `providerEventsPath` and `traceErrorPath` through `exec.py status`.
  `trace.jsonl` records observed UTC timestamps, event IDs, run/parent identities,
  task/workflow identities and attempt numbers in the existing private run directory.
- Follow `child.accepted` to the exact child trace. `loop.transition` links committed
  orchestration revisions, receipt decisions, pending findings and Human skips back to
  the requesting Main run; its `statePath` locates the loop and existing progress history.
- `run.accepted` references the request digest and captured task criteria/authority.
  `prompt.prepared` snapshots the host's fixed and dynamic instructions per attempt.
  `provider.delivery.requested` snapshots prompt-bearing Codex RPCs or Claude/Antigravity
  messages, including host-added instructions and plan/repair/Goal transitions.
  Codex records RPC acknowledgement or failure; CLI adapters record successful pipe writes.
  A pipe write does not prove provider acceptance or model understanding.
- Prompt snapshots are separate `prompt-<id>.json` files; journal entries carry their
  paths and digests. Recognized credentials are masked, with `redacted` and the original
  payload digest recorded explicitly. These are private local diagnostics, not safe
  public exports; masking cannot recognize every possible secret. Environment maps,
  recognized credential fields and encrypted/opaque reasoning fields are masked.
  The runtime does not access provider-internal context or hidden reasoning.
- `provider.event` references exact UTF-8 byte ranges and digests in the existing
  `events.jsonl`, preserving command/tool outputs without duplicating their bodies.
  Ranges and digests address stored, masked bytes; `originalSha256` identifies the
  incoming text and `redacted` indicates a changed representation.
  Observation times belong to runtime ingestion, not necessarily provider execution.
- `result.reported`, `receipt.validated`/`receipt.rejected`, `result.validated` and
  `run.terminal` are distinct. Runtime contract validation establishes structural and
  binding checks, not semantic task correctness or an independent Verification pass.
  The recorded result/receipt digests identify the evidence used at that point.
- Trace writes never grant authority or replace run state. Storage failures leave
  `trace-error.json` where possible and a stderr warning; the diagnostic history is then
  incomplete. A process crash can also leave incomplete evidence. Missing historical
  logs cannot be reconstructed by this feature; no retention deletion is automatic.
- Read the trace or raw events with the existing lossless paging interface. Keep the
  returned `revision` on subsequent pages; restart if a running file changes.

  ```sh
  python3 <plugin-root>/scripts/exec.py status --project-root PROJECT \
    --agent AGENT --run-id RUN --document trace --offset 0 --length 4000
  ```

- Use `--document events` for normalized provider events, `--document provider-events`
  for the protocol journal, or `--document trace-error`
  when a trace error file exists. Older runs without trace references explicitly report
  `read_document_unavailable`. Logging starts when this runtime version executes a run;
  changing a source checkout alone does not update an installed runtime.

### 6.1. Full capture inventory

- Capture covers all messages observed at the instrumented runtime boundaries, with
  no sampling, content-length truncation or automatic deletion. It does not imply that
  a provider reports every internal action. Missing values stay unknown.
- The journal uses local JSONL with explicit schema versions, not OTLP export or a
  claim of full OpenTelemetry compliance. Original managed request/result files remain
  execution artifacts; masking diagnostic copies does not rewrite those contracts.

- JSON serialization preserves event boundaries against log injection. Credential
  masking covers nested JSON arguments, known token formats, bearer authorization,
  password/API-key assignments and CLI flags, credential-bearing URLs and private keys.
  Provider events are decoded content, not a byte-for-byte network packet capture.
- Collection is local; no telemetry upload or new provider API call is introduced.
  Provider-internal actions, unreported model parameters/costs, network packets and
  filesystem changes outside reported tool activity are not inferred or collected.

| Information | Stored evidence |
| --- | --- |
| Correlation | Project, conversation, run, parent run, workflow, task, attempt, event IDs; provider protocol request, thread, turn and tool-call IDs remain in message bodies. |
| Time and writer | UTC observation time, monotonic clock, writer PID/thread, severity; provider timestamp when supplied. Monotonic observations are local-clock measurements, not cross-host timestamps. |
| Runtime | Service/version, Python, OS/architecture; `run.configuration` snapshots captured execution settings, model/effort, capabilities, permissions, task criteria and attachment metadata. |
| Instructions and context | Fixed/dynamic prompt snapshots and delivery revisions; document retrieval metrics in `context.delivered`, with retrieved content in the prepared prompt. |
| Provider protocol | `provider.jsonl` preserves decoded messages before normalization, including unknown fields, model identity, settings, tool definitions, arguments/results, streamed content, finish reasons, usage and provider-reported cost when exposed. Malformed CLI lines are retained with `validJson: false`. |
| Delivery | Codex send/receive notifications and replies, CLI setup/request messages, acknowledgement/failure, measured RPC duration. Pool reuse rebinds logging to the current run. |
| Tool activity | Full reported calls/results and file-change events; item ID/type/name and paired observed start-to-completion duration in the trace index. Unpaired durations remain unknown. |
| Execution | Preflight details, masked launch argv, working directory, PID/exit code, attempt duration, cancellation, retries and worker/adapter exceptions with chained stack traces but no frame locals. |
| Usage and latency | Provider usage plus normalized `usage.observed` snapshots; first normalized event arrival and attempt/RPC durations. First event is not necessarily the first model token. Token subsets are not added again; absent billing is not estimated. |
| Results and decisions | Result and receipt checks, loop revisions, user decisions/skips and `run.final_state` evidence snapshots, including usage, context, permission and error state. State evidence uses `evidence-<id>.json`. |
| Standard error | Complete line-preserving `stderr.log`, with recognized secrets masked across read boundaries, including private-key blocks; terminal trace records its digest. |
| Failure and integrity | Original/stored payload digests, storage-error marker and stderr warnings; these detect some changes but do not constitute a signed, tamper-proof audit log. |

### 6.2. Research basis

- Reviewed on 2026-10-16: [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)
  distinguishes source/observation times, correlation, severity, resource and body.
- [OpenTelemetry GenAI inference conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md)
  and [GenAI agent conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
  informed the model, message, tool, duration and usage inventory. GenAI conventions
  are marked Development; these links are research references, not a pinned schema dependency.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
  informed credential exclusions, safe event encoding, restricted local storage and
  the requirement that diagnostic failures not alter application outcomes.
