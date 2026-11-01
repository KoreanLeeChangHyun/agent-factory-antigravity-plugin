#!/usr/bin/env python3
"""Synchronize selected project Skill hosts from the authoritative docs/skills source."""

import argparse
from contextlib import ExitStack, contextmanager, nullcontext
import difflib
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import subprocess

from export_documents import check_path, inventory


def digest(path):
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Expected regular file: {path}")
    with path.open("rb") as stream:
        result = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".document-sync-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(state_dir):
    lock = state_dir / "lock"
    check_path(lock, state_dir)
    if lock.is_dir():
        # An older installation may still own this directory. Never remove it
        # automatically: that could permit concurrent old and new sync writers.
        raise ValueError(f"Legacy document sync lock; confirm no sync is running before removing: {lock}")
    if lock.exists() and not lock.is_file():
        raise ValueError(f"Expected regular lock file: {lock}")
    # Keep the file in place so all contenders lock the same inode. Closing the
    # descriptor (including process termination) releases the operating-system lock.
    with lock.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError(f"Document sync already running: {lock}") from None
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError(f"Document sync already running: {lock}") from None
        yield


def sync_directory(path):
    # Persist the journal before touching output, including its directory entry.
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def snapshot(path, root):
    entries = inventory(path, root)
    return {name: "dir" if kind == "dir" else "sha256:" + digest(path / name)
            for name, kind in entries.items()}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest key: {key}")
        result[key] = value
    return result


def read_manifest(path, root):
    check_path(path, root)
    if not path.exists():
        # Missing state grants no ownership, even for byte-identical legacy copies.
        return {}
    if not path.is_file():
        raise ValueError(f"Expected regular ownership manifest: {path}")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    return validate_manifest(data)


def validate_manifest(data, *, packages=True):
    if (not isinstance(data, dict) or set(data) != {"version", "entries"}
            or type(data["version"]) is not int or data["version"] != 1
            or not isinstance(data["entries"], dict)):
        raise ValueError("Invalid ownership manifest schema; preserve state and restore a trusted backup")
    entries = data["entries"]
    for name, state in entries.items():
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                or any(ord(char) < 32 for char in name)
                or any(part in ("", ".", "..") for part in name.split("/"))):
            raise ValueError(f"Unsafe manifest path: {name!r}")
        if not isinstance(state, str) or (state != "dir" and not re.fullmatch(r"sha256:[0-9a-f]{64}", state)):
            raise ValueError(f"Invalid manifest state: {name}")
        parts = name.split("/")
        for size in range(1, len(parts)):
            if entries.get("/".join(parts[:size])) != "dir":
                raise ValueError(f"Missing manifest parent: {name}")
        if packages and len(parts) == 1 and (state != "dir" or not isinstance(entries.get(name + "/SKILL.md"), str)
                                or not re.fullmatch(r"sha256:[0-9a-f]{64}", entries[name + "/SKILL.md"])):
            raise ValueError(f"Invalid manifest package: {name}")
    return entries


def document_state(entries):
    return {"version": 1, "entries": entries}


def backup_reconciliation(root, state_dir, target, actual, packages, previous_batch=None):
    """Durably preserve scoped output and control records before any replacement."""
    backups = state_dir / "backups"
    check_path(backups, root)
    backups.mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="reconcile-", dir=backups))
    sync_directory(backups)
    for name, state in sorted(actual.items()):
        if name.split("/")[0] not in packages:
            continue
        destination = backup / "skills" / name
        if state == "dir":
            destination.mkdir(parents=True, exist_ok=True)
            sync_directory(destination.parent)
        else:
            content = (target / name).read_bytes()
            if "sha256:" + hashlib.sha256(content).hexdigest() != state:
                raise ValueError(f"Destination changed during backup: {target / name}")
            atomic_write(destination, content)
    for name in ("manifest.json", "pending.json"):
        path = state_dir / name
        check_path(path, root)
        if path.exists():
            if not path.is_file():
                raise ValueError(f"Expected regular state file: {path}")
            atomic_write(backup / name, path.read_bytes())
    if previous_batch is not None:
        atomic_write(backup / "batch.json", previous_batch)
    atomic_write(backup / "reconciliation.json", json.dumps({
        "source": "docs/skills", "packages": sorted(packages),
        "snapshot": {name: value for name, value in actual.items()
                     if name.split("/")[0] in packages}}, sort_keys=True).encode())
    if (snapshot(target, root) if target.exists() else {}) != actual:
        raise ValueError("Destination changed during backup; no documents replaced")
    return backup


# Agent hosts that load project Skills and the project directory each reads them from; each host
# keeps its own owned output and sync state. The Antigravity CLI (agy) discovers `.agents/skills/`.
HOST_DIRECTORIES = {"codex": ".codex", "claude": ".claude", "antigravity": ".agents"}
HOSTS = tuple(HOST_DIRECTORIES)


def revision(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def freeze_source(root):
    source = root / "docs/skills"
    check_path(source, root)
    if not source.exists():
        return None
    wanted = snapshot(source, root)
    validate_manifest(document_state(wanted))
    contents = {}
    for name, state in wanted.items():
        if state != "dir":
            content = (source / name).read_bytes()
            if "sha256:" + hashlib.sha256(content).hexdigest() != state:
                raise ValueError(f"Source changed while planning: {name}")
            contents[name] = content
    if snapshot(source, root) != wanted:
        raise ValueError("Source changed while planning; retry with a stable source")
    return wanted, contents


def host_snapshot(root, host):
    target = root / HOST_DIRECTORIES[host] / "skills"
    state = target.parent / ".document-sync"
    check_path(target, root)
    controls = {}
    for name in ("manifest.json", "pending.json", "batch.json"):
        path = state / name
        check_path(path, root)
        controls[name] = digest(path)
    return {"entries": snapshot(target, root) if target.exists() else {}, "controls": controls}


def plan_identity(root, hosts, wanted, expected):
    return revision({"root": str(root), "hosts": list(hosts), "source": wanted, "targets": expected})


def read_batch(root, host):
    path = root / HOST_DIRECTORIES[host] / ".document-sync/batch.json"
    check_path(path, root)
    if not path.exists():
        return None
    batch = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(batch, dict) or batch.get("version") != 1 or
            batch.get("status") not in ("applying", "partial", "completed") or
            not isinstance(batch.get("completedHosts"), list)):
        raise ValueError("Invalid sync batch record; preserve it and restore a trusted backup")
    return batch


def classify_file(root, state_dir, source, target, base, wanted, actual):
    if actual == wanted:
        return "converged"
    if actual == base:
        return "source-update"
    if wanted == base:
        return "destination-only"
    if not all(isinstance(item, str) and item.startswith("sha256:") for item in (base, wanted, actual)):
        return "conflict"
    baseline = state_dir / "baselines" / base.removeprefix("sha256:")
    check_path(baseline, root)
    if digest(baseline) != base.removeprefix("sha256:"):
        return "baseline-unavailable"
    original, current, local = baseline.read_bytes(), source.read_bytes(), target.read_bytes()
    if any(b"\0" in value for value in (original, current, local)):
        return "conflict"
    # Git supplies the common-ancestor text merge only; a clean merge conveys no authority.
    with tempfile.TemporaryDirectory(prefix="document-sync-merge-") as folder:
        files = [Path(folder) / part for part in ("source", "base", "destination")]
        for path, data in zip(files, (current, original, local)):
            path.write_bytes(data)
        try:
            merged = subprocess.run(["git", "merge-file", "-p", *map(str, files)],
                                    capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            return "merge-unavailable"
    if merged.returncode == 0:
        return "already-incorporated" if merged.stdout == current else "mergeable"
    return "conflict" if 0 < merged.returncode < 128 else "merge-unavailable"


def status(root, *, hosts=HOSTS):
    """Read-only diagnosis. A disk revision never asserts a running session consumed it."""
    root = root.resolve(strict=True)
    frozen = freeze_source(root)
    wanted = frozen[0] if frozen else {}
    expected, rows = {}, []
    for host in hosts:
        if host not in HOSTS:
            raise ValueError(f"Unknown host: {host}")
        target = root / HOST_DIRECTORIES[host] / "skills"
        state_dir = target.parent / ".document-sync"
        row = {"host": host, "path": str(target.relative_to(root)), "files": [],
               "sessionRevision": None, "backups": []}
        try:
            observed = host_snapshot(root, host)
            expected[host] = observed
            previous = read_manifest(state_dir / "manifest.json", root)
            actual = observed["entries"]
            packages = {name.split("/")[0] for name in wanted.keys() | previous.keys()}
            scoped = {name: value for name, value in actual.items() if name.split("/")[0] in packages}
            row.update(revision=revision(scoped), lastSyncedRevision=revision(previous))
            for name in sorted(wanted.keys() | previous.keys() | scoped.keys()):
                before, source, destination = previous.get(name), wanted.get(name), scoped.get(name)
                if before == source == destination:
                    continue
                package = name.split("/")[0]
                kind = "unowned" if package not in previous and package in actual else classify_file(
                    root, state_dir, root / "docs/skills" / name, target / name,
                    before, source, destination)
                entry = {"path": name, "kind": kind, "base": before, "source": source, "destination": destination}
                if all(isinstance(value, str) and value.startswith("sha256:") for value in (source, destination)):
                    try:
                        entry["diff"] = "".join(difflib.unified_diff(
                            frozen[1][name].decode("utf-8").splitlines(keepends=True),
                            (target / name).read_text(encoding="utf-8").splitlines(keepends=True),
                            fromfile="docs/skills/" + name, tofile=row["path"] + "/" + name))
                    except UnicodeDecodeError:
                        pass
                row["files"].append(entry)
            conflicts = any(item["kind"] != "source-update" for item in row["files"])
            row["state"] = ("source-missing" if frozen is None else "conflict" if conflicts
                            else "outdated" if previous != wanted else "current")
            if observed["controls"]["batch.json"]:
                batch = read_batch(root, host)
                row["batch"] = batch
                if batch.get("status") != "completed":
                    row["state"] = "partial"
            if observed["controls"]["pending.json"]:
                row["state"] = "recovery-required"
            backups = state_dir / "backups"
            check_path(backups, root)
            if backups.exists():
                row["backups"] = [str(path.relative_to(root)) for path in sorted(backups.iterdir())
                                  if path.is_dir() and not path.is_symlink()]
            if host_snapshot(root, host) != observed:
                raise ValueError("Destination changed during diagnosis; refresh status")
        except (OSError, ValueError, TypeError) as error:
            row.update(state="error", error=str(error))
        rows.append(row)
    if frozen and snapshot(root / "docs/skills", root) != wanted:
        raise ValueError("Source changed during diagnosis; refresh status")
    # A button may maintain registered copies, never infer new targets from a host folder.
    sync_hosts = [host for host in hosts if host in expected and expected[host]["controls"]["manifest.json"]]
    return {"sourceRevision": revision(wanted) if frozen else None,
            "planId": plan_identity(root, hosts, wanted, expected) if len(expected) == len(hosts) else None,
            "syncHosts": sync_hosts,
            "syncPlanId": plan_identity(root, sync_hosts, wanted, {host: expected[host] for host in sync_hosts})
                          if frozen and sync_hosts else None,
            "hosts": rows}


def sync(root, *, reconcile=False, hosts=HOSTS, expect_plan=None):
    """Freeze one source, preflight all targets, then apply with cooperating writers locked."""
    root = root.resolve(strict=True)
    hosts = tuple(dict.fromkeys(hosts))
    if any(host not in HOSTS for host in hosts):
        raise ValueError("Unknown host")
    frozen = freeze_source(root)
    if frozen is None:
        return []
    expected = {host: host_snapshot(root, host) for host in hosts}
    plan_id = plan_identity(root, hosts, frozen[0], expected)
    if expect_plan is not None and expect_plan != plan_id:
        raise ValueError("Stale document sync plan; inspect current status before applying")
    errors = []
    for host in hosts:
        try:
            sync_host(root, host, reconcile=reconcile, dry_run=True, frozen=frozen)
        except ValueError as error:
            errors.append(f"{host}: {error}")
    if errors:
        raise ValueError(" | ".join(errors) + " | No host changed.")
    changes = []
    with ExitStack() as locks:
        for host in sorted(hosts):
            state_dir = root / HOST_DIRECTORIES[host] / ".document-sync"
            state_dir.mkdir(parents=True, exist_ok=True)
            locks.enter_context(locked(state_dir))
        for host in hosts:
            if host_snapshot(root, host) != expected[host]:
                raise ValueError(f"Destination changed after planning: {host}; no documents changed")
        if snapshot(root / "docs/skills", root) != frozen[0]:
            raise ValueError("Source changed after planning; no documents changed")
        prior_batches = {}
        for host in hosts:
            path = root / HOST_DIRECTORIES[host] / ".document-sync/batch.json"
            content = path.read_bytes() if path.exists() else None
            if (hashlib.sha256(content).hexdigest() if content is not None else None) != expected[host]["controls"]["batch.json"]:
                raise ValueError(f"Batch record changed after planning: {host}")
            prior_batches[host] = {"batch.json": content}
        batch = {"version": 1, "planId": plan_id, "sourceRevision": revision(frozen[0]),
                 "hosts": list(hosts), "completedHosts": [], "status": "applying"}
        def save_batch():
            for host in hosts:
                atomic_write(root / HOST_DIRECTORIES[host] / ".document-sync/batch.json",
                             json.dumps(batch, sort_keys=True).encode())
        # Avoid changing state for an already-current invocation.
        unfinished = any(expected[host]["controls"]["batch.json"] and
                         read_batch(root, host)["status"] != "completed"
                         for host in hosts)
        if not unfinished and not any(sync_host(root, host, dry_run=True, reconcile=reconcile, frozen=frozen) for host in hosts):
            return []
        save_batch()
        try:
            for host in hosts:
                current = host_snapshot(root, host)
                if (current["entries"] != expected[host]["entries"] or
                        any(current["controls"][name] != expected[host]["controls"][name]
                            for name in ("manifest.json", "pending.json"))):
                    raise ValueError(f"Destination changed after planning: {host}")
                changes += sync_host(root, host, reconcile=reconcile, frozen=frozen, held_lock=True,
                                     control_snapshot=prior_batches[host])
                batch["completedHosts"].append(host)
                save_batch()
            if snapshot(root / "docs/skills", root) != frozen[0]:
                raise ValueError("Source changed during sync")
            for host in hosts:
                if sync_host(root, host, dry_run=True, frozen=frozen):
                    raise ValueError(f"Host changed during final verification: {host}")
            batch["status"] = "completed"
            save_batch()
        except (OSError, ValueError, TypeError) as error:
            batch.update(status="partial", error=str(error))
            save_batch()
            raise
    return changes


def check(root, *, hosts=HOSTS):
    """Report hosts that differ from docs/skills without changing anything."""
    drift, errors = [], []
    for host in hosts:
        try:
            changes = sync_host(root, host, dry_run=True)
            batch = read_batch(root, host)
            if changes or batch and batch["status"] != "completed":
                drift.append(host)
        except ValueError as error:
            errors.append(f"{host}: {error}")
    return drift, errors


def sync_host(root, host, *, reconcile=False, dry_run=False, frozen=None, held_lock=False, control_snapshot=None):
    if host not in HOSTS:
        raise ValueError(f"Unknown host: {host}")
    root = root.resolve(strict=True)
    source = root / "docs/skills"
    target = root / HOST_DIRECTORIES[host] / "skills"
    check_path(source, root)
    if not source.exists():
        return []
    check_path(target, root)
    if target.exists() and not target.is_dir():
        raise ValueError(f"Expected directory: {target}")
    state_dir = root / HOST_DIRECTORIES[host] / ".document-sync"
    check_path(state_dir, root)
    if not dry_run:
        state_dir.mkdir(parents=True, exist_ok=True)
    # A dry run only reads; the real run re-checks everything under the lock.
    with nullcontext() if dry_run or held_lock else locked(state_dir):
        manifest = state_dir / "manifest.json"
        pending = state_dir / "pending.json"
        check_path(pending, root)
        recovery_entries = {}
        if pending.exists() and not reconcile:
            raise ValueError(f"Interrupted document sync: {pending}. Preserve output and journal; "
                             "use --reconcile to back up current output and finish from docs/skills. "
                             "Automatic retry is blocked.")
        if pending.exists():
            if not pending.is_file():
                raise ValueError(f"Expected regular sync journal: {pending}")
            journal = json.loads(pending.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
            if (not isinstance(journal, dict) or set(journal) != {"version", "previous", "planned"}
                    or type(journal["version"]) is not int or journal["version"] != 1):
                raise ValueError("Invalid sync journal; preserve it and restore a trusted backup")
            for key in ("previous", "planned"):
                recovery_entries.update(validate_manifest(document_state(journal[key]), packages=False))
        manifest_invalid = False
        try:
            previous = read_manifest(manifest, root)
        except (ValueError, TypeError):
            # Explicit recovery can reconstruct only source-named packages when
            # ownership is unreadable. Never infer deletions from corrupt state.
            if not reconcile or not manifest.is_file() or manifest.is_symlink():
                raise
            previous = {}
            manifest_invalid = True
        wanted = frozen[0] if frozen else snapshot(source, root)
        for package in source.iterdir():
            if wanted.get(package.name) != "dir" or not wanted.get(package.name + "/SKILL.md", "").startswith("sha256:"):
                raise ValueError(f"Document package needs SKILL.md: {package}")
        validate_manifest(document_state(wanted))
        actual = snapshot(target, root) if target.exists() else {}
        owned = {name for name in previous if "/" not in name}
        requested = {name for name in wanted if "/" not in name}
        conflicts = []
        for package in sorted(owned | requested):
            if package not in owned:
                if package in actual:
                    conflicts.append(f"Unowned destination: {target / package} (identical legacy copies are not adopted)")
                continue
            before = {name: value for name, value in previous.items()
                      if name == package or name.startswith(package + "/")}
            now = {name: value for name, value in actual.items()
                   if name == package or name.startswith(package + "/")}
            for name in sorted(set(before) | set(now)):
                if before.get(name) != now.get(name):
                    conflicts.append(f"Independent destination change: {target / name}")
        if conflicts and not reconcile:
            raise ValueError("; ".join(conflicts) + ". No documents changed. Back up and reconcile "
                             "with --reconcile to preserve existing files and use docs/skills as authoritative.")
        if dry_run:
            outdated = previous != wanted or pending.exists() or bool(conflicts) or manifest_invalid
            return [{"path": str(target.relative_to(root)), "action": "update"}] if outdated else []
        changes = []
        if reconcile and (conflicts or pending.exists() or manifest_invalid):
            packages = owned | requested | {name.split("/")[0] for name in recovery_entries}
            if control_snapshot is None:
                batch_path = state_dir / "batch.json"
                check_path(batch_path, root)
                control_snapshot = {"batch.json": batch_path.read_bytes() if batch_path.exists() else None}
            backup = backup_reconciliation(root, state_dir, target, actual, packages, control_snapshot["batch.json"])
            changes.append({"path": str(backup.relative_to(root)), "action": "backup"})
            previous = {name: value for name, value in actual.items()
                        if name.split("/")[0] in packages}
        if previous == wanted and not pending.exists() and not changes:
            return []
        # Never infer ownership from a partially completed copy. An interrupted run
        # retains both states for explicit recovery and blocks every subsequent write.
        atomic_write(pending, json.dumps({"version": 1, "previous": previous,
                                          "planned": wanted}, sort_keys=True).encode())
        if (snapshot(target, root) if target.exists() else {}) != actual:
            raise ValueError("Destination changed before applying; preserve journal and inspect output")
        def assert_expected(path, expected):
            check_path(path, root)
            found = "dir" if path.is_dir() else "sha256:" + digest(path) if path.exists() else None
            if found != expected:
                raise ValueError(f"Destination changed during sync: {path}; preserve journal")
        for name in sorted(previous, key=lambda value: (len(value.split("/")), value), reverse=True):
            if name not in wanted or (previous[name] == "dir") != (wanted[name] == "dir"):
                path = target / name
                check_path(path, root)
                assert_expected(path, previous[name])
                if previous[name] == "dir":
                    path.rmdir()
                else:
                    path.unlink()
                sync_directory(path.parent)
                changes.append({"path": str(path.relative_to(root)), "action": "delete"})
        target.mkdir(parents=True, exist_ok=True)
        for name, state in sorted(wanted.items()):
            path = target / name
            check_path(path, root)
            if state == "dir":
                if not path.exists():
                    path.mkdir()
                    sync_directory(path.parent)
            elif state != previous.get(name):
                content = frozen[1][name] if frozen else (source / name).read_bytes()
                if "sha256:" + hashlib.sha256(content).hexdigest() != state:
                    raise ValueError(f"Source changed during sync: {source / name}; review {pending}")
                expected_state = previous.get(name)
                if (expected_state == "dir") != (state == "dir"):
                    expected_state = None
                assert_expected(path, expected_state)
                atomic_write(path, content)
                changes.append({"path": str(path.relative_to(root)), "action": "write"})
        if snapshot(source, root) != wanted:
            raise ValueError(f"Source changed during sync; use --reconcile to recover {pending}")
        final = snapshot(target, root)
        managed_packages = {name.split("/")[0] for name in previous} | requested
        expected_final = {name: value for name, value in actual.items() if name.split("/")[0] not in managed_packages}
        expected_final.update(wanted)
        if final != expected_final:
            raise ValueError("Destination changed during sync; preserve journal and inspect output")
        for name, state in wanted.items():
            if state == "dir":
                continue
            baseline = state_dir / "baselines" / state.removeprefix("sha256:")
            check_path(baseline, root)
            content = frozen[1][name] if frozen else (source / name).read_bytes()
            if "sha256:" + hashlib.sha256(content).hexdigest() != state:
                raise ValueError("Source changed while saving baseline; preserve journal")
            if not baseline.exists():
                atomic_write(baseline, content)
            elif "sha256:" + digest(baseline) != state:
                raise ValueError(f"Invalid baseline: {baseline}; preserve journal")
        atomic_write(manifest, json.dumps(document_state(wanted), sort_keys=True).encode())
        pending.unlink()
        sync_directory(state_dir)
        return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--host", action="append", choices=HOSTS,
                        help="Synchronize only this host; repeat to select multiple hosts (default: all hosts).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--reconcile", action="store_true",
                      help="Back up conflicting or interrupted output, then rebuild it from docs/skills.")
    mode.add_argument("--check", action="store_true",
                      help="Report hosts that differ from docs/skills; exit 1 when any differs. Changes nothing.")
    mode.add_argument("--status", action="store_true",
                      help="Read-only file diagnoses, host revisions, recovery state and a guarded plan ID.")
    parser.add_argument("--expect-plan", help="Apply only if source, selected hosts and observed target state still match this status plan ID.")
    args = parser.parse_args()
    hosts = tuple(dict.fromkeys(args.host)) if args.host else HOSTS
    try:
        if args.status:
            print(json.dumps(status(args.project_root, hosts=hosts), ensure_ascii=False))
            return 0
        if args.check:
            drift, errors = check(args.project_root, hosts=hosts)
            print(json.dumps({"hosts": list(hosts), "outdated": drift, "errors": errors}, ensure_ascii=False))
            return 1 if drift or errors else 0
        operations = sync(args.project_root, reconcile=args.reconcile, hosts=hosts, expect_plan=args.expect_plan)
        print(json.dumps({"changes": operations}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
