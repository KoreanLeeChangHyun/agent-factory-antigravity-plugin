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
- After `loop.py start`, wait with `loop.py drive --project-root PROJECT --work-agent ID
  --loop-id LOOP_ID` (or repeated `loop.py status`) until the loop ends, then report the bound
  result. Do not poll run event files.
