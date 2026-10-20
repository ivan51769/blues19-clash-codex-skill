"""Install only an owned, process-scoped Codex HTTP proxy launcher.

Public API (stdlib Python 3.10+):
 default_state_dir() -> pathlib.Path
 prepare(clash_dir, codex_exe, kind, state_dir, proxy_port=None,
         check_listener=True) -> dict
 install(plan, apply=False) -> dict
 restore(state_dir, manifest, apply=False) -> dict

prepare is read-only. install/restore default to read-only preview. All dicts
are JSON serializable; an applied install returns its absolute `manifest` path,
`manifest_data` (a deep copy freezing this generation), and `changed=True`.
Pass `manifest_data` to restore when binding a combined transaction receipt to
an exact generation; the manifest pathname always identifies latest state. ValueError
means unsafe/ambiguous input or state; OSError means an I/O failure. Caller may
restore a successful installation when a larger combined transaction fails.

State is dedicated local data, never the public repository or Clash directory.
Existing state must be owned and hash-identical. Each installation keeps a
hash-checked previous snapshot; restore refuses edits to current or backup
files. Failed installation rolls back its own writes. No original executable,
shortcut, environment, registry, account or profile is modified. TCP preflight
checks connectivity ONLY, not whether a listener is a functioning HTTP proxy.
Windows .cmd is launch-only: it intentionally never expands/forwards arguments;
for CLI arguments invoke the installed Python script directly (argument list).
Its ASCII bootstrap selects console code page 65001 before Unicode paths; this
changes only the attached console code page, not persistent system settings.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import sys
import uuid

ASSET = Path(__file__).resolve().parents[1] / "assets" / "launch_codex.py"
REPOSITORY = Path(__file__).resolve().parents[3]
_runtime = runpy.run_path(str(ASSET))
OWNER = _runtime["OWNER"]
# Public compatibility name; input/state errors are ValueError, I/O stays OSError.
ProxyError = ValueError
safe_path = _runtime["safe_path"]
_read_json = _runtime["read_json"]
WRAPPER = "launch-codex.cmd" if os.name == "nt" else "launch-codex.sh"
FILES = {"config.json", "launch_codex.py", WRAPPER}
MAX_CONFIG = 256 * 1024


def default_state_dir():
    """Return the platform's local-data default without creating it."""
    if os.name == "nt":
        # Packaged assistant hosts can virtualize newly created LOCALAPPDATA
        # paths. A user-home destination remains usable from Explorer/Codex.
        return Path.home() / ".clash-codex-optimizer"
    return Path.home() / ".local" / "share" / "clash-codex-optimizer"


def _json(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _inside(path, root):
    return path == root or root in path.parents


def _state_path(state_dir, clash_dir=None):
    state = safe_path(state_dir)
    if _inside(state, REPOSITORY) or _inside(REPOSITORY, state):
        raise ValueError("Launcher state must be outside the public repository")
    if clash_dir is not None:
        clash = safe_path(clash_dir)
        if _inside(state, clash) or _inside(clash, state):
            raise ValueError("Launcher state must be separate from Clash profiles")
    if state.exists() and not state.is_dir():
        raise ValueError("Launcher state must be a dedicated directory")
    return state


def _port(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r"[0-9]{1,5}", str(value)):
        raise ValueError("Proxy port must be numeric, from 1 through 65535")
    result = int(value)
    if not 1 <= result <= 65535:
        raise ValueError("Proxy port must be numeric, from 1 through 65535")
    return result


def detect_proxy_port(clash_dir):
    """Read only explicit clash_dir/config.yaml, bounded scalar port subset.

    mixed-port wins over port; socks-port and controller are never selected.
    Disabled (0) entries are skipped. Quoted/tagged/aliased ports, duplicate
    top-level keys, root flow collections, directives and multiple documents
    are refused. Nested keys are not interpreted as top-level ports.
    """
    config = safe_path(safe_path(clash_dir) / "config.yaml")
    if not config.is_file() or config.stat().st_size > MAX_CONFIG:
        raise ValueError("Clash config.yaml is missing or exceeds the parser limit")
    try:
        text = config.read_bytes().decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Clash config.yaml must be UTF-8") from exc
    lines = text.splitlines()
    if len(lines) > 8192 or any(len(line) > 8192 for line in lines) or "\x00" in text:
        raise ValueError("Clash config.yaml exceeds the parser limit")
    seen = set()
    ports = {}
    document = False
    content = False
    port_scalar = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line[:len(line) - len(line.lstrip())]:
            raise ValueError("Ambiguous YAML indentation")
        if line[0].isspace():
            if port_scalar:
                raise ValueError("HTTP/mixed port scalar cannot have nested content")
            continue
        clean = line.strip()
        if clean == "---" and not document and not content:
            document = True
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:[ ]+(.*)|[ ]*)", line)
        if not match:
            raise ValueError("Unsupported or ambiguous top-level YAML syntax")
        content = True
        key, value = match.group(1), match.group(2) or ""
        port_scalar = key in ("port", "mixed-port")
        if key in seen:
            raise ValueError("Duplicate top-level YAML key")
        seen.add(key)
        if key in ("port", "mixed-port"):
            scalar = re.fullmatch(r"([0-9]{1,5})(?:[ ]+#.*)?[ ]*", value)
            if not scalar:
                raise ValueError("HTTP/mixed port must be a plain numeric top-level scalar")
            number = int(scalar.group(1))
            if number > 65535:
                raise ValueError("HTTP/mixed port is outside the valid range")
            ports[key] = number
        elif value.lstrip().startswith(("&", "*", "!", "<<")) or key == "_merge":
            raise ValueError("Ambiguous top-level YAML value")
    for key in ("mixed-port", "port"):
        if ports.get(key):
            return ports[key]
    raise ValueError("No enabled top-level HTTP or mixed proxy port; supply an explicit proxy_port")


def _snapshot(state):
    """Capture only known root files, with file modes; backups handled separately."""
    result = {}
    for name in sorted(FILES | {"manifest.json"}):
        p = safe_path(state / name)
        if p.exists():
            if not p.is_file() or p.stat().st_size > _runtime["MAX_JSON"]:
                raise ValueError("Invalid state file")
            result[name] = {"data": base64.b64encode(p.read_bytes()).decode("ascii"), "mode": p.stat().st_mode & 0o777}
    return result


def _tree_hash(state):
    if not state.exists():
        return None
    result = {}
    for p in sorted(state.rglob("*")):
        safe_path(p)
        name = p.relative_to(state).as_posix()
        if p.is_file():
            if p.stat().st_size > _runtime["MAX_JSON"] * 8:
                raise ValueError("Oversized launcher state file")
            result[name] = [_hash(p.read_bytes()), p.stat().st_mode & 0o777]
        elif p.is_dir():
            result[name] = "directory"
        else:
            raise ValueError("Unsupported launcher state entry")
    return result


def _validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) - (FILES | {"manifest.json"}):
        raise ValueError("Invalid backup file set")
    for record in snapshot.values():
        if not isinstance(record, dict) or set(record) != {"data", "mode"} or type(record["mode"]) is not int or not 0 <= record["mode"] <= 0o777:
            raise ValueError("Invalid backup record")
        try:
            base64.b64decode(record["data"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid backup encoding") from exc
    return snapshot


def _managed(state):
    if not state.exists():
        return None
    # Empty directories are not adopted: they have no ownership marker.
    manifest = _read_json(state / "manifest.json")
    if not isinstance(manifest, dict) or set(manifest) != {"owner", "version", "files", "backups", "previous", "created_directory"}:
        raise ValueError("Unmanaged launcher directory")
    if manifest["owner"] != OWNER or type(manifest["version"]) is not int or manifest["version"] != 1 or type(manifest["created_directory"]) is not bool:
        raise ValueError("Invalid launcher ownership manifest")
    if not isinstance(manifest["files"], dict) or set(manifest["files"]) != FILES:
        raise ValueError("Invalid owned file set")
    backups = manifest["backups"]
    if not isinstance(backups, dict) or not backups or not isinstance(manifest["previous"], str) or manifest["previous"] not in backups:
        raise ValueError("Invalid backup inventory")
    if set(p.name for p in state.iterdir()) != FILES | {"manifest.json", "backups"}:
        raise ValueError("Custom files in launcher directory; refusing changes")
    backup_root = safe_path(state / "backups")
    if not backup_root.is_dir() or set(p.name for p in backup_root.iterdir()) != set(backups):
        raise ValueError("Custom or missing backup entries")
    for token, digest in backups.items():
        if not re.fullmatch(r"[0-9a-f]{32}", token):
            raise ValueError("Invalid backup identifier")
        directory = safe_path(backup_root / token)
        if not directory.is_dir() or set(p.name for p in directory.iterdir()) != {"snapshot.json"}:
            raise ValueError("Custom or missing backup files")
        p = safe_path(directory / "snapshot.json")
        if not p.is_file() or p.stat().st_size > _runtime["MAX_JSON"] or _hash(p.read_bytes()) != digest:
            raise ValueError("Backup was edited; refusing changes")
        _validate_snapshot(_read_json(p))
    for name, digest in manifest["files"].items():
        p = safe_path(state / name)
        if not p.is_file() or p.stat().st_size > _runtime["MAX_JSON"] or _hash(p.read_bytes()) != digest:
            raise ValueError("Launcher file was edited; refusing changes")
    return manifest


def _wrapper(python, state):
    script = str(state / "launch_codex.py")
    if os.name == "nt":
        # No expansion of user arguments, delayed expansion or cmd metacharacters.
        if any(c in python + script for c in '%!^&|<>()"\r\n'):
            raise ValueError("Unsafe Windows wrapper path; use paths without shell metacharacters")
        return ('@echo off\r\nsetlocal DisableDelayedExpansion\r\n'
                'rem Console-local UTF-8 bootstrap; no persistent system setting is changed.\r\n'
                '"%SystemRoot%\\System32\\chcp.com" 65001 >nul\r\n'
                'if errorlevel 1 exit /b 1\r\n'
                'rem Launch only; pass CLI arguments by invoking the Python script directly.\r\n'
                '"' + python + '" -I "' + script + '"\r\nexit /b %errorlevel%\r\n')
    return '#!/bin/sh\nexec ' + shlex.quote(python) + ' -I ' + shlex.quote(script) + ' "$@"\n'


def prepare(clash_dir, codex_exe, kind, state_dir, proxy_port=None, check_listener=True):
    """Build a read-only JSON-serializable installation plan. No files created."""
    if kind in ("electron", "owl") and os.name != "nt":
        raise ValueError("Desktop running-instance verification is unsupported on this platform; choose CLI")
    clash = safe_path(clash_dir)
    if not clash.is_dir():
        raise ValueError("Explicit Clash directory does not exist")
    state = _state_path(state_dir, clash)
    executable = _runtime["validate_executable"](str(safe_path(codex_exe)), kind)
    port = _port(proxy_port) if proxy_port is not None else detect_proxy_port(clash)
    if check_listener:
        _runtime["check_listener"](port)
    _managed(state)
    # Normal system Python installations may expose a symlink; persist its real
    # interpreter target, while all state/target executable links stay refused.
    python = str(safe_path(Path(sys.executable).resolve()))
    config = {"owner": OWNER, "version": 1, "codex_exe": str(executable), "kind": kind,
              "proxy_url": "http://127.0.0.1:" + str(port), "python_exe": python}
    _runtime["validate_config"](config)
    files = {"config.json": _json(config).decode("utf-8"), "launch_codex.py": ASSET.read_bytes().decode("utf-8"),
             WRAPPER: _wrapper(python, state)}
    return {"owner": OWNER, "state_dir": str(state), "clash_dir": str(clash), "files": files,
            "before": _tree_hash(state), "check_listener": bool(check_listener),
            "compatibility": "unverified-owl-proxy-flag" if kind == "owl" else "process-scoped-proxy-not-routing-verified",
            "warnings": (["EXPERIMENTAL Owl: Chromium proxy flag compatibility and routing are unverified."] if kind == "owl" else []) + ["TCP listener checks do not prove HTTP proxy functionality.",
                         "Desktop proxy launch requires a recognized desktop bundle and no existing instance; Owl remains unverified.",
                         "The Windows cmd wrapper is launch-only; use Python directly for CLI arguments.",
                         "The Windows wrapper switches its attached console to UTF-8 code page 65001; no persistent system setting is changed."]}


def _atomic(path, data, mode=0o600):
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temp.open("xb") as stream:
            stream.write(data)
        temp.chmod(mode)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _put_snapshot(state, snapshot):
    for name in FILES | {"manifest.json"}:
        p = state / name
        if name in snapshot:
            record = snapshot[name]
            _atomic(p, base64.b64decode(record["data"], validate=True), record["mode"])
        elif p.exists():
            p.unlink()


def _capture_tree(state, manifest):
    """Capture only validated owned entries, never concurrent unknown files."""
    directories = ["backups"] + ["backups/" + token for token in manifest["backups"]]
    names = sorted(FILES | {"manifest.json"}) + [name + "/snapshot.json" for name in directories[1:]]
    files = {}
    for name in names:
        path = safe_path(state / name)
        files[name] = (path.read_bytes(), path.stat().st_mode & 0o777)
    return directories, files


def _recover_tree(state, captured):
    # Never recursively delete: unknown files appearing concurrently survive.
    safe_path(state).mkdir(parents=True, exist_ok=True, mode=0o700)
    directories, files = captured
    for name in sorted(directories, key=lambda value: len(Path(value).parts)):
        safe_path(state / name).mkdir(exist_ok=True, mode=0o700)
    for name, (data, mode) in files.items():
        _atomic(safe_path(state / name), data, mode)


def _remove_created_tree(directory, expected):
    """Remove only an exact tree created by this operation; fail closed on edits."""
    if _tree_hash(directory) != expected:
        raise ValueError("Concurrent or custom state appeared; refusing unsafe rollback cleanup")
    for name in sorted(expected, key=lambda value: len(Path(value).parts), reverse=True):
        path = safe_path(directory / name)
        if expected[name] == "directory":
            path.rmdir()
        else:
            if not path.is_file() or [_hash(path.read_bytes()), path.stat().st_mode & 0o777] != expected[name]:
                raise ValueError("Concurrent state edit; refusing unsafe rollback cleanup")
            path.unlink()
    directory.rmdir()


def install(plan, apply=False):
    """Preview/apply a prepared plan; rollback this operation on write failure."""
    if not isinstance(plan, dict) or plan.get("owner") != OWNER or not isinstance(plan.get("files"), dict) or set(plan["files"]) != FILES:
        raise ValueError("Invalid launcher plan")
    state = _state_path(plan["state_dir"], plan["clash_dir"])
    _managed(state)
    if _tree_hash(state) != plan["before"]:
        raise ValueError("Launcher state changed since prepare")
    # Do not permit plan tampering to replace the public launcher with arbitrary code.
    if plan["files"]["launch_codex.py"].encode("utf-8") != ASSET.read_bytes():
        raise ValueError("Plan launcher differs from public template")
    config = json.loads(plan["files"]["config.json"])
    _runtime["validate_config"](config)
    if plan["files"][WRAPPER] != _wrapper(config["python_exe"], state):
        raise ValueError("Plan wrapper differs from safe template")
    result = {"manifest": str(state / "manifest.json"), "state_dir": str(state), "changed": False,
              "launcher": str(state / WRAPPER), "proxy_url": config["proxy_url"], "kind": config["kind"],
              "compatibility": plan["compatibility"], "files": sorted(FILES), "warnings": plan["warnings"]}
    if not apply:
        return result
    if plan["check_listener"]:
        _runtime["check_listener"](_runtime["proxy_port"](config["proxy_url"]))
    old = _managed(state)
    snapshot = _snapshot(state)
    token = uuid.uuid4().hex
    backup = state / "backups" / token
    created = not state.exists()
    owns_state = False
    owns_backup = False
    created_tree = {}
    backup_tree = {}

    def record(path, data):
        entry = [_hash(data), path.stat().st_mode & 0o777]
        created_tree[path.relative_to(state).as_posix()] = entry
        if path.parent == backup:
            backup_tree[path.name] = entry

    try:
        if created:
            state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # The leaf must be exclusive: never adopt/delete a directory that
            # another process creates after our read-only preflight.
            state.mkdir(mode=0o700)
            owns_state = True
            (state / "backups").mkdir(mode=0o700)
            created_tree["backups"] = "directory"
        backup.mkdir(mode=0o700)
        owns_backup = True
        created_tree["backups/" + token] = "directory"
        snapshot_data = _json(snapshot)
        _atomic(backup / "snapshot.json", snapshot_data)
        record(backup / "snapshot.json", snapshot_data)
        for name, text in plan["files"].items():
            data = text.encode("utf-8")
            _atomic(state / name, data, 0o700 if name == "launch-codex.sh" else 0o600)
            record(state / name, data)
        backups = dict(old["backups"]) if old else {}
        backups[token] = _hash(snapshot_data)
        manifest = {"owner": OWNER, "version": 1, "files": {name: _hash(text.encode("utf-8")) for name, text in plan["files"].items()},
                    "backups": backups, "previous": token, "created_directory": created}
        manifest_bytes = _json(manifest)
        _atomic(state / "manifest.json", manifest_bytes)
        record(state / "manifest.json", manifest_bytes)
    except BaseException:
        if owns_state:
            _remove_created_tree(state, created_tree)
        elif not created:
            _put_snapshot(state, snapshot)
            if owns_backup:
                _remove_created_tree(backup, backup_tree)
        # Never remove shared parent directories or a leaf we did not create.
        raise
    result["changed"] = True
    result["manifest_data"] = json.loads(json.dumps(manifest))
    return result


def restore(state_dir, manifest, apply=False):
    """Guard hashes, then restore the immediately preceding owned state.

    manifest: absolute manifest path returned by install, or its parsed dict.
    Restore is itself rollback-protected against an interrupted write operation.
    """
    state = _state_path(state_dir)
    current = _managed(state)
    if current is None:
        raise ValueError("No owned launcher installation to restore")
    if isinstance(manifest, (str, os.PathLike)):
        if safe_path(manifest) != state / "manifest.json":
            raise ValueError("Manifest must belong to this state directory")
        supplied = _read_json(manifest)
    else:
        supplied = manifest
    if supplied != current:
        raise ValueError("Restore manifest does not match current installation")
    backup = state / "backups" / current["previous"]
    snapshot = _validate_snapshot(_read_json(backup / "snapshot.json"))
    if current["created_directory"] and snapshot:
        raise ValueError("Invalid initial installation snapshot")
    if not current["created_directory"] and set(snapshot) != FILES | {"manifest.json"}:
        raise ValueError("Incomplete previous installation snapshot")
    result = {"state_dir": str(state), "changed": False, "files": sorted(FILES)}
    if not apply:
        return result
    before = _capture_tree(state, current)
    expected_backup = {"snapshot.json": [current["backups"][current["previous"]],
                                         (backup / "snapshot.json").stat().st_mode & 0o777]}
    try:
        _put_snapshot(state, snapshot)
        # Delete only this known backup inventory, never unknown concurrent files.
        # Keep cleanup inside compensation: even a partial unlink must restore
        # the exact pre-operation snapshot bytes and current manifest.
        _remove_created_tree(backup, expected_backup)
        if current["created_directory"]:
            (state / "backups").rmdir()
            state.rmdir()
    except BaseException:
        _recover_tree(state, before)
        raise
    result["changed"] = True
    return result
