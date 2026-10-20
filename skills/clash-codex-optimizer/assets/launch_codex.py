#!/usr/bin/env python3
"""Owned, process-only Codex proxy launcher (Python 3.10+; no third-party modules).

TCP connectivity proves only that a listener exists, not that it is an HTTP proxy.
The parent environment, shortcuts, registry, accounts and application files are
never changed. Foreground launch refuses an existing desktop. Explicit repair
permits one identity-checked graceful close/start, never force termination.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
import math

OWNER = "clash-codex-optimizer/process-proxy/v1"
BYPASS = "localhost,127.0.0.1,::1"
MAX_JSON = 1024 * 1024


def safe_path(path):
    """Return an absolute Path, refusing symlinks and Windows reparse points."""
    p = Path(os.path.abspath(os.fspath(path)))
    for item in (p, *p.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Links and junctions are not supported")
    return p


def read_json(path):
    p = safe_path(path)
    if not p.is_file() or p.stat().st_size > MAX_JSON:
        raise ValueError("Missing or oversized launcher state")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate state key")
            result[key] = value
        return result
    try:
        return json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid launcher state") from exc


def proxy_port(proxy_url):
    if not isinstance(proxy_url, str) or not re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}", proxy_url):
        raise ValueError("Proxy must be an explicit loopback HTTP URL")
    port = int(proxy_url.rsplit(":", 1)[1])
    if port > 65535:
        raise ValueError("Invalid proxy port")
    return port


def validate_executable(executable, kind):
    if kind not in ("cli", "electron", "owl"):
        raise ValueError("Codex kind must be cli, electron or explicit experimental owl")
    if not isinstance(executable, str) or not Path(executable).is_absolute():
        raise ValueError("Codex executable must be an absolute path")
    p = safe_path(executable)
    if not p.is_file():
        raise ValueError("Codex executable must be an existing regular file")
    if p.suffix.lower() in (".cmd", ".bat"):
        raise ValueError("Shell wrappers are not executable targets")
    if os.name == "nt":
        if p.suffix.lower() != ".exe":
            raise ValueError("Windows executable must have .exe extension")
    elif not os.access(p, os.X_OK):
        raise ValueError("Codex executable is not executable")
    if kind in ("electron", "owl"):
        resources = safe_path(p.parent / "resources")
        asar = safe_path(resources / "app.asar")
        package = safe_path(resources / "app" / "package.json")
        marker = safe_path(resources / "owl-electron-app.json")
        owl = False
        if marker.exists():
            metadata = read_json(marker)
            if not isinstance(metadata, dict) or not isinstance(metadata.get("runtimeName"), str):
                raise ValueError("Ambiguous desktop runtime metadata")
            owl = metadata["runtimeName"].casefold() == "owl"
        if kind == "electron" and owl:
            raise ValueError("Owl runtime is not verified standard Electron; select explicit experimental owl kind")
        if kind == "owl" and not owl:
            raise ValueError("Experimental owl kind requires resources/owl-electron-app.json runtimeName owl")
        if not (asar.is_file() or package.is_file()):
            raise ValueError("Desktop requires adjacent resources/app.asar or resources/app/package.json")
    return p


def validate_config(config):
    if not isinstance(config, dict) or set(config) != {"owner", "version", "codex_exe", "kind", "proxy_url", "python_exe"}:
        raise ValueError("Unexpected launcher configuration shape")
    if config["owner"] != OWNER or type(config["version"]) is not int or config["version"] != 1:
        raise ValueError("Launcher ownership marker is invalid")
    validate_executable(config["codex_exe"], config["kind"])
    proxy_port(config["proxy_url"])
    python = config["python_exe"]
    if not isinstance(python, str) or not Path(python).is_absolute() or not safe_path(python).is_file():
        raise ValueError("Python interpreter is unavailable")
    if os.path.normcase(str(Path(sys.executable).resolve())) != os.path.normcase(str(Path(python).resolve())):
        raise ValueError("Launcher must use its installed Python interpreter")
    return config


def check_listener(port, timeout=1.0):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            pass
    except OSError as exc:
        raise ValueError("No TCP listener on the selected loopback proxy port") from exc


def child_environment(parent, proxy_url):
    """child_environment(parent: Mapping[str,str], proxy_url: str) -> dict.

    Inherit the runtime environment only in memory; never mutate parent or store
    inherited values in config. NO_PROXY deliberately contains loopback only.
    """
    proxy_port(proxy_url)
    env = dict(parent)
    # Remove case variants too: Windows environment names are case-insensitive.
    names = {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    for key in list(env):
        if key.lower() in names:
            del env[key]
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env[key] = proxy_url
    env["NO_PROXY"] = env["no_proxy"] = BYPASS
    return env


def desktop_running(executable):
    """Windows CIM path-based check; fail closed if unavailable/ambiguous.

    The fixed command never queries CommandLine, embeds a user path or starts a
    shell. Results are filtered locally by name then exact executable path.
    """
    if os.name != "nt":
        raise ValueError("Desktop running-instance verification is unsupported on this platform; CLI is supported")
    root = os.environ.get("SystemRoot", r"C:\Windows")
    powershell = safe_path(Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")
    if not powershell.is_file():
        raise ValueError("Cannot verify existing desktop instances")
    command = ("$ErrorActionPreference='Stop'; "
               "@(Get-CimInstance Win32_Process | Select-Object Name,ExecutablePath) | "
               "ConvertTo-Json -Compress")
    try:
        result = subprocess.run([str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                                shell=False, capture_output=True, text=True, timeout=10, check=True)
        if len(result.stdout) > MAX_JSON:
            raise ValueError("Oversized process inventory")
        rows = json.loads(result.stdout)
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValueError("Invalid process inventory")
        target = os.path.normcase(os.path.abspath(str(executable)))
        name = Path(executable).name.casefold()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"Name", "ExecutablePath"} or not isinstance(row["Name"], str):
                raise ValueError("Invalid process inventory")
            if row["Name"].casefold() == name:
                path = row["ExecutablePath"]
                if not isinstance(path, str) or not Path(path).is_absolute():
                    raise ValueError("Cannot verify a matching desktop process path")
                if os.path.normcase(os.path.abspath(path)) == target:
                    return True
        return False
    except (OSError, subprocess.SubprocessError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot verify existing desktop instances") from exc


def load_owned_config(config_path):
    config_path = safe_path(config_path)
    if config_path.name != "config.json":
        raise ValueError("Launcher expects its dedicated config.json")
    manifest = read_json(config_path.parent / "manifest.json")
    if (not isinstance(manifest, dict)
            or set(manifest) != {"owner", "version", "files", "backups", "previous", "created_directory"}
            or manifest.get("owner") != OWNER or type(manifest.get("version")) is not int
            or manifest["version"] != 1 or type(manifest.get("created_directory")) is not bool
            or not isinstance(manifest.get("backups"), dict) or not isinstance(manifest.get("previous"), str)
            or manifest["previous"] not in manifest["backups"]):
        raise ValueError("Launcher ownership manifest is invalid")
    files = manifest.get("files")
    wrapper = "launch-codex.cmd" if os.name == "nt" else "launch-codex.sh"
    if not isinstance(files, dict) or set(files) != {"config.json", "launch_codex.py", wrapper}:
        raise ValueError("Launcher manifest file set is invalid")
    for name, digest in files.items():
        p = safe_path(config_path.parent / name)
        if not p.is_file() or p.stat().st_size > MAX_JSON or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError("Owned launcher files were edited; refusing launch")
    return validate_config(read_json(config_path))


def build_command(config, args=()):
    """Shared argv builder; never changes process state or the environment."""
    argv = list(args)
    if any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
        raise ValueError("Invalid child arguments")
    command = [config["codex_exe"]]
    if config["kind"] in ("electron", "owl"):
        if any(arg.lower().startswith(("--proxy", "--no-proxy", "--host-resolver")) for arg in argv):
            raise ValueError("Proxy override arguments are not supported")
        command += ["--proxy-server=" + config["proxy_url"], "--proxy-bypass-list=localhost;127.0.0.1;[::1]"]
    return command + argv


def launch(config_path, args=()):
    """Existing foreground CLI/desktop launcher; never repairs implicitly."""
    config = load_owned_config(config_path)
    check_listener(proxy_port(config["proxy_url"]))
    argv = list(args)
    if any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
        raise ValueError("Invalid child arguments")
    if config["kind"] in ("electron", "owl"):
        if config["kind"] == "owl":
            print("WARNING: unverified-owl-proxy-flag: Owl proxy flag compatibility and routing are unverified.", file=sys.stderr)
        if desktop_running(config["codex_exe"]):
            raise ValueError("Codex desktop is already running; quit it yourself before using this launcher. No proxy activation was attempted")
    return subprocess.run(build_command(config, argv), shell=False,
                          env=child_environment(os.environ, config["proxy_url"])).returncode


MAX_WINDOWS = 32
POLL_INTERVAL = 0.1


def process_inventory():
    """Read-only, fixed CIM query: no command lines, arguments or environments.

    Kept separate from desktop_running to preserve the foreground API's probe.
    CreationDate is retained verbatim as an opaque process incarnation token.
    """
    if os.name != "nt":
        raise ValueError("Windows desktop only")
    powershell = safe_path(Path(os.environ.get("SystemRoot", r"C:\Windows")) /
                           "System32/WindowsPowerShell/v1.0/powershell.exe")
    if not powershell.is_file():
        raise ValueError("Process inventory unavailable")
    command = ("$ErrorActionPreference='Stop'; "
               "@(Get-CimInstance Win32_Process | Select-Object Name,ExecutablePath,ProcessId,ParentProcessId,"
               "@{Name='Created';Expression={if ($null -ne $_.CreationDate) "
               "{$_.CreationDate.ToUniversalTime().ToString('o')}}}) | ConvertTo-Json -Compress")
    result = subprocess.run([str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                            shell=False, capture_output=True, text=True, timeout=10, check=True)
    if len(result.stdout) > MAX_JSON:
        raise ValueError("Oversized process inventory")
    rows = json.loads(result.stdout)
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise ValueError("Invalid process inventory")
    return rows


def matching_processes(executable):
    """Fail closed for any same-name process whose exact identity is unknown."""
    target = os.path.normcase(os.path.abspath(str(executable)))
    name = Path(executable).name.casefold()
    matches = {}
    for row in process_inventory():
        if not isinstance(row, dict) or not isinstance(row.get("Name"), str):
            raise ValueError("Invalid process inventory")
        if row["Name"].casefold() != name:
            continue
        path, pid, ppid, created = (row.get(key) for key in
                                  ("ExecutablePath", "ProcessId", "ParentProcessId", "Created"))
        if (not isinstance(path, str) or not Path(path).is_absolute()
                or os.path.normcase(os.path.abspath(path)) != target
                or type(pid) is not int or pid <= 0 or type(ppid) is not int or ppid < 0
                or not isinstance(created, str) or not created or pid in matches):
            raise ValueError("Desktop process identity inaccessible or ambiguous")
        matches[pid] = (pid, ppid, created, target)
    return matches


def browser_root(processes):
    roots = [identity for identity in processes.values() if identity[1] not in processes]
    if len(roots) != 1:
        raise ValueError("Desktop browser root is ambiguous")
    return roots[0]


def desktop_windows(pid):
    """Enumerate only visible top-level HWNDs for the selected browser PID."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    windows = []
    @callback_type
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            windows.append(int(hwnd))
        return len(windows) <= MAX_WINDOWS
    if not user32.EnumWindows(visit, 0) or len(windows) > MAX_WINDOWS:
        raise ValueError("Window enumeration failed or exceeded limit")
    return windows


def post_close(hwnd, pid):
    """Post WM_CLOSE, never interact with dialogs or kill a process."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    if owner.value != pid or not user32.IsWindowVisible(hwnd):
        raise ValueError("Window ownership changed")
    if not user32.PostMessageW(hwnd, 0x0010, 0, 0):
        raise ValueError("Graceful close refused")


def claim_action(config_path, action_id):
    """Exclusive, permanent one-shot ledger shared by sibling state directories.

    Never overwrite, retry or remove a token, including after an I/O failure.
    Only generic ownership/action metadata is stored, never paths or config.
    """
    if not isinstance(action_id, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", action_id):
        raise ValueError("Action ID must be exactly 32 hex characters")
    directory = safe_path(Path(config_path).parent.parent / ".clash-codex-actions")
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError:
        pass
    directory = safe_path(directory)
    if not directory.is_dir():
        raise ValueError("Invalid action ledger directory")
    token = safe_path(directory / (action_id.lower() + ".json"))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(token, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump({"owner": OWNER, "action": "repair-desktop"}, stream)
        stream.flush()
        os.fsync(stream.fileno())


def repair_desktop(config_path, action_id, close_timeout=20, start_timeout=15):
    """Explicit one-shot Windows desktop repair, not a readiness/ComputerUse test.

    Status describes process observations only. Only 'started' includes a verified
    original-child root pid; started_at is epoch seconds immediately before Popen.
    No retries, force termination, prompt interaction, exit wait, inherited output
    capture or global changes. ComputerUse capability remains unknown.
    Adapter exceptions intentionally become generic, JSON-safe failure codes.
    """
    result = {"status": "preflight_failed", "pid": None, "started_at": None,
              "close_attempted": False, "start_attempted": False, "compatibility": "unverified",
              "gui_ready": False, "workspace_ready": False, "computer_use_ready": False}
    phase = "preflight_failed"
    try:
        if (os.name != "nt" or not isinstance(action_id, str)
                or not re.fullmatch(r"[0-9a-fA-F]{32}", action_id)):
            return result
        for timeout in (close_timeout, start_timeout):
            if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                    or not math.isfinite(timeout) or timeout <= 0 or timeout > 300):
                return result
        config_path = safe_path(config_path)
        config = load_owned_config(config_path)
        if config["kind"] not in ("electron", "owl"):
            return result
        result["compatibility"] = "unverified-owl-proxy-flag" if config["kind"] == "owl" else "unverified"
        command = build_command(config)
        env = child_environment(os.environ, config["proxy_url"])
        check_listener(proxy_port(config["proxy_url"]))
        executable = config["codex_exe"]
        original = matching_processes(executable)
        root = browser_root(original) if original else None
        windows = desktop_windows(root[0]) if root else []
        if root and (not windows or len(windows) > MAX_WINDOWS or len(set(windows)) != len(windows)):
            result["status"] = "no_safe_windows"
            return result
        phase = "action_claim_failed"
        claim_action(config_path, action_id)
        phase = "identity_changed"
        if matching_processes(executable) != original:
            raise ValueError("Desktop changed before action")
        if root:
            deadline = time.monotonic() + close_timeout
            for hwnd in windows:
                if time.monotonic() >= deadline:
                    result["status"] = "close_timeout"
                    return result
                current = matching_processes(executable)
                if (current.get(root[0]) != root
                        or any(original.get(pid) != identity for pid, identity in current.items())):
                    raise ValueError("Desktop changed before close")
                if time.monotonic() >= deadline:
                    result["status"] = "close_timeout"
                    return result
                result["close_attempted"] = True
                phase = "close_refused"
                post_close(hwnd, root[0])
                phase = "identity_changed"
            while True:
                if time.monotonic() >= deadline:
                    result["status"] = "close_timeout"
                    return result
                current = matching_processes(executable)
                if any(original.get(pid) != identity for pid, identity in current.items()):
                    raise ValueError("Competing desktop or PID reuse")
                if time.monotonic() >= deadline:
                    result["status"] = "close_timeout"
                    return result
                if not current:
                    break
                time.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))
        # Do not reuse the pre-close snapshot, even after observing an empty set.
        if matching_processes(executable):
            raise ValueError("Competing desktop before launch")
        if root and time.monotonic() >= deadline:
            result["status"] = "close_timeout"
            return result
        phase = "start_failed"
        result["start_attempted"] = True
        result["started_at"] = float(time.time())
        # Desktop logs are inspected separately through a redacting observer;
        # never leak inherited application output into a diagnostic JSON stream.
        child = subprocess.Popen(command, shell=False, env=env,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + start_timeout
        observed = None
        phase = "start_unknown"
        while time.monotonic() < deadline:
            current = matching_processes(executable)
            identity = current.get(child.pid)
            exited = child.poll() is not None
            if exited:
                result["status"] = "start_handoff" if current else "start_early_exit"
                return result
            if identity:
                if observed is not None and observed != identity:
                    result["status"] = "start_identity_changed"
                    return result
                observed = identity
                if browser_root(current) == identity:
                    # Recheck both incarnation and original Popen handle state.
                    confirmed = matching_processes(executable)
                    if child.poll() is not None:
                        result["status"] = "start_handoff" if confirmed else "start_early_exit"
                    elif confirmed.get(child.pid) == observed and browser_root(confirmed) == observed:
                        result["status"] = "started"
                        result["pid"] = child.pid
                    else:
                        result["status"] = "start_identity_changed"
                    return result
            elif current:
                result["status"] = "start_handoff"
                return result
            time.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))
        result["status"] = "start_timeout"
    except (ValueError, OSError, subprocess.SubprocessError, UnicodeError, TypeError):
        result["status"] = phase
    return result


def main():
    try:
        return launch(Path(__file__).absolute().parent / "config.json", sys.argv[1:])
    except (ValueError, OSError) as exc:
        print("Codex proxy launcher: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
