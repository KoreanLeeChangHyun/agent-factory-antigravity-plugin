# Agent Factory

These rules apply only when you perform an Agent Factory operation (managed Work or
Verification, Documents, conventions or plugin tools). Ordinary conversations are unaffected.

- Act as Agent Factory Main. Your role contract is `skills/agent/prompt/main.md` in this
  plugin; read it once before the first managed operation of a conversation.
- `<plugin-root>` is this installed plugin directory (it holds `skills/`, `runtime/` and
  `scripts/`); on this host it is normally `~/.gemini/config/plugins/agent-factory`.
- Dispatch with the exact commands in the `agent` Skill's "Managed execution quick path".
  Write the bounded request to a file first and pass it with `--request-file`.
- Never read `runtime/` or `scripts/` source, `--help` output of unrelated commands, or run
  `doctor`/`capabilities` merely to learn how to submit. The Skill and its linked reference
  are the contract.
- After `loop.py start`, preserve accepted IDs and follow Main's captured task route and
  completion/reporting contract. Acceptance is not completion; do not impose a separate
  wait on routes that require returning after acceptance. When that contract calls for
  observing a loop, use `loop.py status` or `loop.py drive --project-root PROJECT
  --work-agent ID --loop-id LOOP_ID`. Do not poll run event files.
