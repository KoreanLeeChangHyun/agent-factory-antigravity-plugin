"""Test settings, per-user dependencies and saved project environments.

Detection is read-only and probes an actual Chromium launch. Setup alone may
download pinned dependencies; it never installs into the target checkout.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.request import urlopen
import zipfile

from execution import test_harness as harness
from storage import paths
from storage.errors import ContractError
from storage.files import file_lock

NODE_VERSION = "24.21.0"
PLAYWRIGHT_VERSION = "1.61.1"
PROFILE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


def tools_home(home=None):
    return paths.home_path(home) / "tools" / "testing"


def environment(home=None):
    """One environment for detection, installation and the detached supervisor."""
    target = tools_home(home)
    env = dict(os.environ)
    node_dir = target / "node" / ("" if os.name == "nt" else "bin")
    if (node_dir / ("node.exe" if os.name == "nt" else "node")).is_file():
        env["PATH"] = str(node_dir) + os.pathsep + env.get("PATH", "")
    module = target / "node_modules" / "playwright"
    if (module / "package.json").is_file():
        env.setdefault("PLAYWRIGHT_MODULE", str(module))
    # Chromium goes to the recommended folder too, not the shared ~/.cache/ms-playwright other projects use.
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(target.parent / "browsers"))
    return env


def run(argv, env, timeout=45):
    try:
        result = subprocess.run(argv, cwd=Path.home(), env=env, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise ContractError("dependency_failed", (result.stderr or result.stdout).strip()[-12000:] or f"{argv[0]} exited {result.returncode}")
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContractError("dependency_failed", str(error)) from error


def node_probe(env):
    node = shutil.which("node", path=env.get("PATH"))
    if not node:
        raise ContractError("node_unavailable", "Node.js is missing")
    version = run([node, "--version"], env)
    match = re.match(r"v(\d+)\.", version)
    if not match or int(match[1]) < 20:
        raise ContractError("node_unsupported", "Playwright requires Node.js 20 or newer")
    return node, version


def doctor(args):
    env = environment(args.runtime_home)
    dependencies = []
    try:
        node, version = node_probe(env)
        dependencies.append({"id": "node", "available": True, "version": version, "path": node})
    except ContractError as error:
        node = None
        dependencies.append({"id": "node", "available": False, "error": str(error)})
    module = None
    try:
        # Only a chosen package or the recommended one counts; other projects' node_modules are never borrowed.
        module = env.get("PLAYWRIGHT_MODULE") or str(tools_home(args.runtime_home) / "node_modules" / "playwright")
        if not (Path(module) / "package.json").is_file():
            raise ContractError("playwright_unavailable", f"Playwright is not installed in the recommended folder {module}")
        package = json.loads((Path(module) / "package.json").read_text(encoding="utf-8"))
        dependencies.append({"id": "playwright", "available": True, "version": package["version"], "path": module})
    except (ContractError, OSError, ValueError, KeyError) as error:
        module = None
        dependencies.append({"id": "playwright", "available": False, "error": str(error)})
    try:
        if not node or not module:
            raise ContractError("browser_unavailable", "Node.js and Playwright are required")
        source = "const {chromium}=require(process.argv[1]); (async()=>{const b=await chromium.launch({executablePath:process.env.AGENT_FACTORY_CHROMIUM_PATH||undefined}); console.log(JSON.stringify({version:b.version(),path:process.env.AGENT_FACTORY_CHROMIUM_PATH||chromium.executablePath()})); await b.close()})().catch(e=>{console.error(String(e));process.exit(1)})"
        browser = json.loads(run([node, "-e", source, module], env))
        dependencies.append({"id": "chromium", "available": True, **browser})
    except (ContractError, ValueError) as error:
        dependencies.append({"id": "chromium", "available": False, "error": str(error)})
    return {"schemaVersion": 1, "kind": "test-dependencies", "ready": all(d["available"] for d in dependencies),
            "dependencies": dependencies, "managedPath": str(tools_home(args.runtime_home))}


def download_node(target):
    system = {"Linux": "linux", "Darwin": "darwin", "Windows": "win"}.get(platform.system())
    architecture = {"x86_64": "x64", "AMD64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine())
    if not system or not architecture:
        raise ContractError("unsupported_platform", "Install Node.js 20+ on this platform and retry")
    stem = f"node-v{NODE_VERSION}-{system}-{architecture}"
    filename = stem + (".zip" if system == "win" else ".tar.gz")
    base = f"https://nodejs.org/dist/v{NODE_VERSION}/"
    with tempfile.TemporaryDirectory(prefix="af-test-node-", dir=target) as temporary:
        temporary = Path(temporary)
        archive = temporary / filename
        with urlopen(base + "SHASUMS256.txt", timeout=60) as response:
            sums = response.read().decode()
        expected = next((line.split()[0] for line in sums.splitlines() if line.split()[-1] == filename), None)
        if not expected:
            raise ContractError("download_failed", "Official Node.js checksum is missing")
        with urlopen(base + filename, timeout=120) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise ContractError("download_failed", "Node.js SHA256 verification failed")
        if system == "win":
            with zipfile.ZipFile(archive) as package:
                if any(not (temporary / item.filename).resolve().is_relative_to(temporary) for item in package.infolist()):
                    raise ContractError("download_failed", "Unsafe Node.js archive")
                package.extractall(temporary)
        else:
            with tarfile.open(archive) as package:
                for member in package.getmembers():
                    if not (temporary / member.name).resolve().is_relative_to(temporary) or member.isdev() or member.isfifo():
                        raise ContractError("download_failed", "Unsafe Node.js archive")
                    if (member.issym() or member.islnk()) and not (temporary / member.name).parent.joinpath(member.linkname).resolve().is_relative_to(temporary):
                        raise ContractError("download_failed", "Unsafe Node.js archive link")
                if hasattr(tarfile, "data_filter"):
                    package.extractall(temporary, filter="data")
                else:
                    # Python 3.10 before the extraction-filter backport. Recheck
                    # each path after earlier links have actually been created.
                    for member in package.getmembers():
                        destination = temporary / member.name
                        link = temporary / member.linkname if member.islnk() else destination.parent / member.linkname
                        if (not destination.resolve().is_relative_to(temporary)
                                or (member.issym() or member.islnk()) and not link.resolve().is_relative_to(temporary)
                                or not (member.isfile() or member.isdir() or member.issym() or member.islnk())):
                            raise ContractError("download_failed", "Unsafe Node.js archive")
                        package.extract(member, temporary)
        destination = target / "node"
        if destination.exists():
            raise ContractError("node_install_conflict", "Managed Node.js is damaged; select a working Node.js path in Providers")
        (temporary / stem).rename(destination)


def setup(args):
    target = tools_home(args.runtime_home)
    paths.mkdir(target)
    with file_lock(target / ".setup.lock"):
        status = doctor(args)
        if status["ready"]:
            return status
        env = environment(args.runtime_home)
        try:
            node, _ = node_probe(env)
        except ContractError:
            download_node(target)
            env = environment(args.runtime_home)
            node, _ = node_probe(env)
        if not status["dependencies"][1]["available"]:
            # Prefer npm's JS entrypoint to .cmd shell execution on Windows.
            candidates = [Path(node).parent / "node_modules/npm/bin/npm-cli.js", Path(node).parent.parent / "lib/node_modules/npm/bin/npm-cli.js"]
            npm_cli = next((path for path in candidates if path.is_file()), None)
            npm = shutil.which("npm", path=env.get("PATH"))
            if not npm_cli and npm and os.name != "nt":
                resolved = Path(npm).resolve()
                npm_cli = resolved if resolved.name == "npm-cli.js" else None
            if not npm_cli and os.name == "nt":
                npm_cli = Path(npm).parent / "node_modules/npm/bin/npm-cli.js" if npm else None
            argv = [node, str(npm_cli)] if npm_cli and npm_cli.is_file() else [npm] if npm and os.name != "nt" else None
            if not argv:
                if (target / "node").exists():
                    raise ContractError("npm_unavailable", "Managed npm is damaged; configure a working npm path in Providers and retry")
                download_node(target)
                env = environment(args.runtime_home)
                node, _ = node_probe(env)
                npm_cli = target / "node" / ("node_modules/npm/bin/npm-cli.js" if os.name == "nt" else "lib/node_modules/npm/bin/npm-cli.js")
                argv = [node, str(npm_cli)]
            run([*argv, "install", "--prefix", str(target), "--no-audit", "--no-fund", "--ignore-scripts", f"playwright@{PLAYWRIGHT_VERSION}"], env, 600)
            env = environment(args.runtime_home)
        from system.browser import playwright_module
        module = env.get("PLAYWRIGHT_MODULE") or playwright_module(Path(args.project_root))
        run([node, str(Path(module) / "cli.js"), "install", "chromium"], env, 600)
        result = doctor(args)
        if not result["ready"]:
            raise ContractError("browser_launch_failed", next(d["error"] for d in result["dependencies"] if not d["available"]))
        return result


def profiles_directory(args):
    return Path(harness.root_binding(args)["runtimeRoot"]) / "test-environments"


def profile_path(args, profile):
    if not isinstance(profile, str) or not PROFILE_ID.fullmatch(profile) or profile in (".", ".."):
        raise ContractError("invalid_profile", "Invalid environment ID")
    path = profiles_directory(args) / (profile + ".json")
    paths.inspect(path, missing=True)
    return path


def configure(args, data):
    harness.validate(data, harness.MANIFEST_SCHEMA, "environment")
    harness.freeze_manifest(Path(args.project_root).resolve(), data)
    target = profile_path(args, args.profile)
    paths.mkdir(target.parent)
    paths.write(target, data)
    return snapshot(args)


def snapshot(args):
    binding = harness.root_binding(args)
    directory = profiles_directory(args)
    profiles = []
    if directory.exists():
        paths.inspect(directory)
        profiles = [{"id": p.stem, "manifest": paths.read(p)} for p in sorted(directory.glob("*.json"))]
    sessions = []
    session_root = Path(binding["runtimeRoot"]) / "test-sessions"
    if session_root.exists():
        paths.inspect(session_root)
        for path in session_root.glob("test-*/state.json"):
            state = paths.read(path)
            sessions.append({key: state.get(key) for key in ("session", "name", "executionStatus", "outcome", "automationVerdict", "humanVerdict", "startedAt")})
    return {"schemaVersion": 1, "kind": "test-settings", "profiles": profiles,
            "sessions": sorted(sessions, key=lambda x: x.get("startedAt") or "", reverse=True)}
