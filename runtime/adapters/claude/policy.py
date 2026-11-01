"""Claude permission mapping and unrestricted host readiness check."""
import json

from execution import policy as execution_policy
from storage.errors import ContractError
from hooks import orchestrator_guard, subagent_guard, team_inbox
from execution import tool_server_launch
from .capabilities import EFFORTS, EFFORT_ALIASES

# Nearest Claude permission mode for each Agent Factory sandbox type. Claude tool permissions are
# not an OS sandbox: network access is not confined and writable_roots only extend tool access.
PERMISSION_MODES = {"danger-full-access": "bypassPermissions", "workspace-write": "acceptEdits", "read-only": "dontAsk"}
# Claude's configured permissions.defaultMode -> inherited sandbox type. "default" asks before
# each change and "plan"/"dontAsk" never change files, so none of them grants write access.
POLICY_FOR_MODE = {"bypassPermissions": "danger-full-access", "acceptEdits": "workspace-write", "auto": "workspace-write",
                   "default": "read-only", "plan": "read-only", "dontAsk": "read-only"}


def validate(session):
    model = session.get("model")
    if model and (not isinstance(model, str) or not model.startswith("claude-") or any(c.isspace() for c in model)):
        raise ContractError("provider_model_mismatch", "Claude model must be a claude-* identifier")
    requested = session.get("reasoningEffort")
    if requested not in (None, "") and requested not in EFFORTS and requested not in EFFORT_ALIASES:
        raise ContractError("reasoning_effort_invalid", f"Claude does not support reasoning effort {requested!r}")


def effort(value):
    if value in EFFORTS:
        return value
    return EFFORT_ALIASES.get(value)


def permission_arguments(session, working_directory):
    policy = execution_policy.session_policy(session)["sandboxPolicy"]
    arguments = ["--permission-mode", PERMISSION_MODES[policy["type"]], "--permission-prompts", "none"]
    if policy["type"] == "workspace-write":
        for root in policy.get("writable_roots", []):
            if str(root) != str(working_directory):
                arguments += ["--add-dir", str(root)]
    return arguments


def work_subagent_arguments():
    """Work may start only the read-only Explore sub-agent; every other sub-agent type is denied.

    Claude's `Agent(type)` allowlist applies only to a `--agent` main thread and deny rules name single
    types, so a PreToolUse hook decides. Hooks run before the permission mode, so the denial holds under
    bypassPermissions, acceptEdits, dontAsk and plan. Workflow scripts start sub-agents without the
    Agent tool, so that tool is removed."""
    return ["--disallowedTools", "Workflow"]


def work_subagent_hook():
    return {"matcher": subagent_guard.MATCHER,
            "hooks": [{"type": "command", "command": subagent_guard.HOOK_COMMAND, "timeout": 30}]}


def settings_arguments(pre_tool_use=()):
    """One settings payload per launch: the PreToolUse guards the role needs and, for every run, the
    PostToolUse hook that delivers queued team messages next to each tool result while the run works."""
    hooks = {"PostToolUse": [{"hooks": [{"type": "command", "command": team_inbox.HOOK_COMMAND, "timeout": 10}]}]}
    if pre_tool_use:
        hooks["PreToolUse"] = list(pre_tool_use)
    return ["--settings", json.dumps({"hooks": hooks})]


def team_tools(plugin_root):
    """Provider-neutral team messages and shared memory, and the native tools of the local tool server.
    The server checks each call against the run's role and policy."""
    return [*(f"Bash(python3 {plugin_root / 'scripts' / name} *)" for name in ("messages.py", "memory.py")),
            "mcp__" + tool_server_launch.NAME]


def tool_server_arguments():
    """The plugin's standard actions as native tools for this run, next to any servers the user configured."""
    command = tool_server_launch.command("claude")
    config = {"mcpServers": {tool_server_launch.NAME: {"type": "stdio", "command": command[0], "args": command[1:]}}}
    return ["--mcp-config", json.dumps(config)]


def inspection_arguments(plugin_root):
    """Allow only the existing read-only inspectors, including their page options, and the team tools."""
    script = str(plugin_root / "scripts" / "exec.py")
    inspectors = [f"Bash(python3 {script} {command} *)" for command in ("status", "list")]
    return ["--allowedTools", ",".join([*inspectors, *team_tools(plugin_root)])]


# Read-only Git inspection shared by every allowlist below.
GIT_READS = ["Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git show*)"]


def orchestrator_arguments(plugin_root, run_directory):
    """Orchestrate Main reads/confirms links, writes own records and runs guarded managed scripts.

    The run's sandbox policy is unchanged so delegated Work keeps its own permissions."""
    # Claude permission rules spell absolute paths with a leading "//".
    run_files = "/" + str(run_directory) + "/**"
    # Web tools support bounded known-context fact/link confirmation.
    tools = ["Read", "Grep", "Glob", "WebSearch", "WebFetch", f"Edit({run_files})", f"Write({run_files})",
             f"Bash(python3 {plugin_root}/scripts/*)", "mcp__" + tool_server_launch.NAME, *GIT_READS]
    return ["--permission-mode", "dontAsk", "--permission-prompts", "none", "--allowedTools", ",".join(tools)]


def orchestrator_hook():
    return {"matcher": "Bash|Write|Edit|MultiEdit", "hooks": [
        {"type": "command", "command": orchestrator_guard.HOOK_COMMAND, "timeout": 30}]}
