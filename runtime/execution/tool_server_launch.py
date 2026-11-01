"""How each provider starts the local tool server for a run: one command, configured per provider."""
from __future__ import annotations

import sys
from pathlib import Path

NAME = "agent-factory"
# Codex names servers in TOML keys and tool prefixes; it keeps to word characters.
CODEX_NAME = "agent_factory"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tool_server.py"
# Long actions (dispatch, test sessions, captures) must not be cut off by a provider's default tool timeout.
TOOL_TIMEOUT_SECONDS = 3600
# Codex starts MCP servers with only HOME, PATH, LANG, LOGNAME, SHELL and USER; the commands behind the tools
# also need these when present. Without the systemd user manager (XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS)
# loop.py cannot start a durable loop driver (observed 2026-10-28: driver_launch_failed). The calling run's
# parent state and policy are never forwarded: the server sets them for each call.
FORWARDED_ENVIRONMENT = (
    "AGENT_FACTORY_HOME", "AGENT_FACTORY_DEV_PLUGIN_ROOT", "AGENT_FACTORY_CODEX_POOL", "AGENT_FACTORY_HOLDS",
    "AF_CODEX_CAPABILITY_CACHE", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "XDG_CACHE_HOME", "XDG_STATE_HOME", "TMPDIR", "CODEX_HOME", "CLAUDE_CONFIG_DIR", "PLAYWRIGHT_MODULE",
    "PLAYWRIGHT_BROWSERS_PATH", "DISPLAY", "WAYLAND_DISPLAY", "SSH_AUTH_SOCK", "LC_ALL", "LC_CTYPE", "TERM",
    "NODE_PATH", "NVM_DIR", "VIRTUAL_ENV", "UV_CACHE_DIR",
    "AGENT_FACTORY_IMAGE_TIMEOUT",
)


def command(host: str) -> list[str]:
    return [sys.executable or "python3", str(SCRIPT), "--host", host]
