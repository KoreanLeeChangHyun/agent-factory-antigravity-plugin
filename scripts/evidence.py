#!/usr/bin/env python3
"""Evidence for an AI's own debugging and testing in any project: screen captures with browser logs, checks compared
with a saved baseline, and exclusive holds on a shared test environment.

The Human is not asked to check what these can show (Convention verification-environment).
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from execution.cli import JsonArgumentParser, add_project_argument  # noqa: E402
from storage import paths as runtime_paths  # noqa: E402
from storage.errors import ContractError  # noqa: E402
from storage.artifacts import artifact_output  # noqa: E402
from storage.files import atomic_write_json, emit, error_document, file_lock, now, safe_read_json  # noqa: E402

NAME = "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"

# Runs in Node with an already installed Playwright; argv[1] is the JSON request. Prints one JSON line.
CAPTURE_SCRIPT = r"""
const request = JSON.parse(process.argv[1]);
const { chromium } = require(request.module);
(async () => {
  const log = [];
  const at = () => new Date().toISOString();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: request.viewport, deviceScaleFactor: request.scale });
    page.on('console', message => log.push({ at: at(), type: 'console', level: message.type(), text: message.text() }));
    page.on('pageerror', error => log.push({ at: at(), type: 'pageerror', text: String(error && error.stack || error) }));
    page.on('requestfailed', item => log.push({ at: at(), type: 'requestfailed', url: item.url(), error: item.failure() && item.failure().errorText }));
    page.on('response', response => { if (response.status() >= 400) log.push({ at: at(), type: 'http', status: response.status(), url: response.url() }); });
    const response = await page.goto(request.url, { waitUntil: 'load', timeout: request.timeoutMs });
    if (request.waitFor) await page.locator(request.waitFor).first().waitFor({ timeout: request.timeoutMs });
    for (const selector of request.clicks) {
      await page.locator(selector).first().click({ timeout: request.timeoutMs });
      log.push({ at: at(), type: 'click', selector });
    }
    if (request.waitMs) await page.waitForTimeout(request.waitMs);
    await page.evaluate(() => document.fonts && document.fonts.ready);
    const target = request.element ? page.locator(request.element).filter({ visible: true }).first() : page;
    await target.screenshot({ path: request.out, fullPage: !request.element && request.fullPage, animations: 'disabled', timeout: request.timeoutMs });
    console.log(JSON.stringify({ status: response ? response.status() : null, title: await page.title(), url: page.url(), log }));
  } finally { await browser.close(); }
})().catch(error => { console.log(JSON.stringify({ error: String(error && error.message || error) })); process.exit(1); });
"""


def build_parser():
    parser = JsonArgumentParser(prog="evidence.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    capture = commands.add_parser("capture", help="Screenshot a page or local file with an installed Playwright and save its browser log")
    add_project_argument(capture)
    capture.add_argument("--target", required=True, help="http(s) URL or a local HTML/SVG/image file path")
    capture.add_argument("--out", type=Path, required=True, help="PNG path; the browser log is written beside it as <name>.log.json")
    capture.add_argument("--viewport", default="1280x800", help="WIDTHxHEIGHT in CSS pixels")
    capture.add_argument("--scale", type=float, default=1.0, help="Device scale factor")
    capture.add_argument("--wait-for", help="CSS selector that must appear before anything else")
    capture.add_argument("--click", action="append", default=[], help="CSS selector clicked before the capture; repeat in order")
    capture.add_argument("--wait-ms", type=int, default=0, help="Extra settle time after the clicks")
    capture.add_argument("--element", help="Capture only the first visible element matching this selector")
    capture.add_argument("--full-page", action="store_true", help="Capture the whole scrollable page")
    capture.add_argument("--timeout-sec", type=int, default=30)

    checks = commands.add_parser("checks", help="Run named checks in parallel and compare them with this project's saved baseline")
    add_project_argument(checks)
    checks.add_argument("--check", action="append", default=[], metavar="NAME=COMMAND", help="A check run by the shell in the project root; repeat")
    checks.add_argument("--file", type=Path, help='JSON {"checks":[{"name","command","cwd"?}]} with more checks')
    checks.add_argument("--set", default="default", help="Baseline name, for separate check groups")
    checks.add_argument("--jobs", type=int, default=4)
    checks.add_argument("--timeout-sec", type=int, default=600)
    checks.add_argument("--save-baseline", action="store_true", help="Store this run as the baseline of --set")

    hold = commands.add_parser("hold", help="Run a command while holding a named shared test environment; other holders wait")
    add_project_argument(hold)
    hold.add_argument("--name", required=True, help="Environment name, such as dev-server or sandbox-app")
    hold.add_argument("--purpose", required=True, help="What the holder is doing, shown to sessions that wait")
    hold.add_argument("--wait-sec", type=int, default=3600)
    hold.add_argument("argv", nargs="+", metavar="-- COMMAND", help="The command and its arguments")
    return parser


def write_json(path: Path, value: dict) -> None:
    """Evidence files go where the caller chose (project artifacts or temp), outside the managed runtime."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def project_storage(args) -> tuple[Path, Path]:
    binding = runtime_paths.resolve(args.project_root, home=args.runtime_home, project_id=args.project_id)
    if not binding["registered"]:
        raise ContractError("project_uninitialized", "project has no registered runtime")
    return Path(binding["projectRoot"]), Path(binding["runtimeRoot"])


def named(value: str, what: str) -> str:
    import re
    if not re.match(NAME, value):
        raise ContractError("name_invalid", f"{what} must match {NAME}")
    return value


def playwright_module(project_root: Path) -> str:
    """An installed Node Playwright: PLAYWRIGHT_MODULE, the project and its ancestors, their sibling projects, global npm."""
    explicit = os.environ.get("PLAYWRIGHT_MODULE")
    if explicit:
        return explicit
    candidates = []
    home = Path.home().resolve()
    for directory in [project_root.resolve(), *project_root.resolve().parents]:
        candidates.append(directory / "node_modules" / "playwright")
        if directory != project_root.resolve() and directory != Path(directory.anchor):
            try:
                candidates += [child / "node_modules" / "playwright" for child in sorted(directory.iterdir()) if child.is_dir()]
            except OSError:
                pass
        if directory == home:
            break
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=20).stdout.strip()
        if root:
            candidates.append(Path(root) / "playwright")
    except (OSError, subprocess.SubprocessError):
        pass
    for candidate in candidates:
        if (candidate / "package.json").is_file():
            return str(candidate)
    raise ContractError("playwright_unavailable", "No installed Node Playwright was found in the project, its ancestors and their "
                        "sibling projects, or global npm. Set PLAYWRIGHT_MODULE to an installed node_modules/playwright; "
                        "installing one needs the Human's approval.")


def capture(args) -> dict:
    project_root, _ = project_storage(args)
    target = args.target
    if not target.startswith(("http://", "https://", "file://")):
        path = Path(target).expanduser()
        path = path if path.is_absolute() else project_root / path
        if not path.is_file():
            raise ContractError("capture_target_missing", f"No such file: {path}")
        target = path.resolve().as_uri()
    try:
        width, height = (int(part) for part in args.viewport.lower().split("x"))
    except ValueError as error:
        raise ContractError("viewport_invalid", "--viewport must be WIDTHxHEIGHT") from error
    try:
        out = artifact_output(args.out, project_root)
    except ValueError as error:
        raise ContractError("capture_output_invalid", str(error)) from error
    if out.suffix.lower() != ".png" or not out.parent.is_dir():
        raise ContractError("capture_output_invalid", "--out must be a .png path in an existing directory")
    request = {"module": playwright_module(project_root), "url": target, "out": str(out), "viewport": {"width": width, "height": height},
               "scale": args.scale, "waitFor": args.wait_for, "clicks": args.click, "waitMs": args.wait_ms,
               "element": args.element, "fullPage": args.full_page, "timeoutMs": args.timeout_sec * 1000}
    try:
        finished = subprocess.run(["node", "-e", CAPTURE_SCRIPT, json.dumps(request)], capture_output=True, text=True,
                                  timeout=args.timeout_sec * 4 + 60, cwd=str(project_root))
    except FileNotFoundError as error:
        raise ContractError("node_unavailable", "Node.js is required to run Playwright") from error
    lines = [line for line in finished.stdout.splitlines() if line.startswith("{")]
    reply = json.loads(lines[-1]) if lines else {"error": (finished.stderr or finished.stdout).strip()[-800:]}
    if reply.get("error"):
        raise ContractError("capture_failed", reply["error"])
    log_path = out.with_name(out.stem + ".log.json")
    write_json(log_path, {"schemaVersion": 1, "target": target, "capturedAt": now(), **reply})
    problems = [item for item in reply["log"] if item["type"] in ("pageerror", "requestfailed", "http") or item.get("level") == "error"]
    return {"screenshot": str(out), "log": str(log_path), "status": reply["status"], "title": reply["title"],
            "problems": len(problems), "firstProblems": problems[:5]}


def read_checks(args, project_root: Path) -> list[dict]:
    checks = []
    for item in args.check:
        name, separator, command = item.partition("=")
        if not separator or not command.strip():
            raise ContractError("check_invalid", "--check must be NAME=COMMAND")
        checks.append({"name": named(name.strip(), "check name"), "command": command})
    if args.file:
        document = safe_read_json(args.file if args.file.is_absolute() else project_root / args.file)
        for item in document.get("checks", []):
            checks.append({"name": named(str(item.get("name", "")), "check name"), "command": str(item["command"]),
                           **({"cwd": str(item["cwd"])} if item.get("cwd") else {})})
    names = [check["name"] for check in checks]
    if not checks or len(set(names)) != len(names):
        raise ContractError("checks_invalid", "Give at least one check, each with a unique name")
    return checks


def run_checks(args) -> tuple[dict, int]:
    project_root, storage = project_storage(args)
    checks = read_checks(args, project_root)
    named(args.set, "--set")
    logs = Path(tempfile.mkdtemp(prefix="af-checks-"))

    def run(check: dict) -> dict:
        started = time.monotonic()
        cwd = project_root / check.get("cwd", ".")
        log = logs / f"{check['name']}.log"
        with log.open("w", encoding="utf-8") as stream:
            try:
                code = subprocess.run(check["command"], shell=True, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                      timeout=args.timeout_sec).returncode
            except subprocess.TimeoutExpired:
                code = "timeout"
        ok = code == 0
        result = {"name": check["name"], "ok": ok, "seconds": round(time.monotonic() - started, 1)}
        if not ok:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            result.update(exit=code, log=str(log), tail=lines[-5:])
        else:
            log.unlink()
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = sorted(pool.map(run, checks), key=lambda item: item["name"])
    baseline_path = storage / f"check-baseline-{args.set}.json"
    baseline = safe_read_json(baseline_path) if baseline_path.is_file() else None
    before = {item["name"]: item["ok"] for item in (baseline or {}).get("results", [])}
    failed = [item for item in results if not item["ok"]]
    document = {"set": args.set, "passed": len(results) - len(failed), "total": len(results),
                "baseline": str(baseline_path) if baseline else None, "baselineAt": (baseline or {}).get("at"),
                "newFailures": [item for item in failed if before.get(item["name"]) is not False] if baseline else failed,
                "existingFailures": [item["name"] for item in failed if before.get(item["name"]) is False],
                "nowPassing": [item["name"] for item in results if item["ok"] and before.get(item["name"]) is False],
                "results": results, "logs": str(logs)}
    # Logs are kept for the failures that need a look; the baseline already explains the others.
    for item in results:
        if not item["ok"] and item["name"] in document["existingFailures"]:
            Path(item.pop("log")).unlink(missing_ok=True)
    if args.save_baseline:
        atomic_write_json(baseline_path, {"schemaVersion": 1, "set": args.set, "at": now(),
                                          "results": [{"name": item["name"], "ok": item["ok"]} for item in results]})
        document["savedBaseline"] = str(baseline_path)
    if not any(path.exists() for path in logs.iterdir()):
        logs.rmdir()
        document["logs"] = None
    return document, (1 if document["newFailures"] else 0)


def hold(args) -> int:
    _, storage = project_storage(args)
    name = named(args.name, "--name")
    command = args.argv[1:] if args.argv and args.argv[0] == "--" else args.argv
    if not command:
        raise ContractError("hold_command_missing", "Give the command after --")
    held = [item for item in os.environ.get("AGENT_FACTORY_HOLDS", "").split(",") if item]
    if name in held:  # The holder's own nested commands run inside its hold.
        return subprocess.call(command)
    info = storage / f"hold-{name}.json"
    deadline = time.monotonic() + args.wait_sec
    announced = False
    while True:
        try:
            with file_lock(storage / f"hold-{name}.lock", blocking=False):
                atomic_write_json(info, {"schemaVersion": 1, "name": name, "purpose": args.purpose, "pid": os.getpid(), "since": now()})
                try:
                    environment = {**os.environ, "AGENT_FACTORY_HOLDS": ",".join([*held, name])}
                    return subprocess.call(command, env=environment)
                finally:
                    info.unlink(missing_ok=True)
        except ContractError as error:
            if error.code != "lock_busy":
                raise
        if time.monotonic() > deadline:
            holder = safe_read_json(info) if info.is_file() else {}
            raise ContractError("hold_busy", f"{name} stayed held by {holder.get('purpose', 'another session')} since {holder.get('since', '?')}")
        if not announced:
            holder = safe_read_json(info) if info.is_file() else {}
            print(f"waiting for {name}: held by {holder.get('purpose', 'another session')} since {holder.get('since', '?')}", file=sys.stderr)
            announced = True
        time.sleep(2)


def main(argv=None):
    try:
        args = build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
        if args.command == "hold":
            return hold(args)
        if args.command == "capture":
            emit(capture(args))
            return 0
        document, code = run_checks(args)
        emit(document)
        return code
    except ContractError as error:
        emit(error_document(error.code, error.message))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
