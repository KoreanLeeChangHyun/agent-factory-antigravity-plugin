# Native image generation

Call the native `imagegen` MCP tool with a `prompt` when image generation is requested.
It starts the installed Codex app-server, verifies an existing ChatGPT login, and asks
Codex's built-in `image_gen` tool to generate the image. No API key, arbitrary backend
command, credential extraction or direct authenticated HTTP call is used. The invocation
consumes the existing Codex account's usage limits; it is not a separate free allowance.

Codex must be on PATH and signed in with ChatGPT. `CODEX_HOME`, when set, selects the
existing Codex configuration and login directory. The integration requires app-server
`imageGeneration` events with image bytes. API-key login, missing Codex, missing tool
output and failed generations return explicit errors. Text claiming success, filenames
and URLs do not count as generated images. There is no API or Gemini fallback.

The image-only child has a new ephemeral thread, read-only sandbox, no approval prompts,
and disabled shell, hooks, plugins, apps and subagent tools. Configured MCP servers are
disabled for that thread to avoid recursively invoking this image tool. The user's
existing conversations and configuration files are not changed.

Every returned image reaches MCP as an image content block. Claude runtime events preserve
the bytes for the chat's image display confirmation. Tool completion alone does not prove
that the image was displayed. The original native output stays in Codex's generated-image
storage; the chat retains image bytes in its run events.

`AGENT_FACTORY_IMAGE_TIMEOUT` sets the total timeout in seconds (default 300). A failed or
timed-out invocation is never automatically retried or redirected to another provider.
Display retry reuses the existing bytes. Only writable Work runs and direct Main runs may
call this tool through MCP. The script can also be called with `--prompt`; the invoking
runtime retains responsibility for authorization, as with other plugin scripts.
