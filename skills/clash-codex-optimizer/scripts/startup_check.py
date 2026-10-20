"""Bounded, read-only observation of fresh Codex desktop startup logs.

Only known desktop logger events are classified. Component resolution, local
backend readiness, TCP/HTTP responses and arbitrary Computer Use text NEVER
establish Computer Use readiness. Raw records and paths are not returned.
"""

from datetime import datetime, timezone
import os
import math
from pathlib import Path
import re
import stat
import time

MAX_FILES = 64
MAX_ENTRIES = 2048
MAX_DEPTH = 4
MAX_LINE = 16384
MAX_BYTES = 1024 * 1024
MAX_FILE_BYTES = 128 * 1024
LINE = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))\s+(info|warning|warn|error|debug)\s+(?:\[([^\]\r\n]+)\]\s+)?(.*)$')
PID_FILE = re.compile(r'^codex-desktop-[0-9a-fA-F-]{36}-(\d+)-t\d+-i\d+-\d{6}-\d+\.log$')


def safe_path(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Startup logs cannot use symlink/junction paths.')
    return path


def list_logs(root):
    root = safe_path(root)
    if not root.is_dir():
        raise ValueError('An explicit existing Codex desktop Logs directory is required.')
    pending = [(root, 0)]
    files = []
    visited = 0
    limited = False
    while pending:
        folder, depth = pending.pop()
        safe_path(folder)
        with os.scandir(folder) as entries:
            for entry in entries:
                visited += 1
                if visited > MAX_ENTRIES:
                    limited = True
                    pending.clear()
                    break
                path = Path(entry.path)
                safe_path(path)
                if entry.is_dir(follow_symlinks=False) and depth < MAX_DEPTH:
                    pending.append((path, depth + 1))
                elif entry.is_file(follow_symlinks=False) and path.suffix.lower() == '.log':
                    # Windows DirEntry.stat may report zero inode/device IDs;
                    # use os.stat through Path for comparison with opened fstat.
                    info = path.stat(follow_symlinks=False)
                    files.append((path, info))
    files.sort(key=lambda item: item[1].st_mtime_ns, reverse=True)
    return files[:MAX_FILES], limited or len(files) > MAX_FILES


def capture(log_dir):
    """Capture file identities/EOF offsets without reading log contents."""
    now = time.time()
    if log_dir is None:
        return {'root': None, 'files': {}, 'captured_at': now, 'bytes_read': 0, 'limited': False}
    root = safe_path(log_dir)
    files, limited = list_logs(root)
    states = {}
    for path, info in files:
        states[str(path)] = {'identity': (info.st_dev, info.st_ino), 'offset': info.st_size, 'carry': b''}
    return {'root': str(root), 'files': states, 'captured_at': now, 'bytes_read': 0, 'limited': limited}


def field(message, key, value):
    return re.search(r'(?:^|\s)' + re.escape(key) + r'=(?:' + re.escape(value) + r'|"' + re.escape(value) + r'")(?:\s|$)', message) is not None


def classify(line, not_before, expected_pid, source_pid, now=None):
    """Return a whitelisted event code, never original text/metadata.

    PID is taken only from the known desktop log filename, not untrusted message
    values. Unknown filename formats remain unattributed instead of ready.
    """
    if type(expected_pid) is not int or expected_pid <= 0 or source_pid != expected_pid:
        return None
    match = LINE.fullmatch(line)
    if not match:
        return None
    timestamp, severity, logger, message = match.groups()
    try:
        event_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).astimezone(timezone.utc).timestamp()
    except ValueError:
        return None
    now = time.time() if now is None else now
    if event_time < not_before or event_time > now + 5:
        return None
    if logger == 'AppServerConnection':
        if message.startswith('initialize_handshake_result ') and field(message, 'outcome', 'success') and field(message, 'transportKind', 'stdio'):
            return 'local_backend_handshake_success'
        if message.startswith('app_server_connection.state_changed ') and field(message, 'hostId', 'local') and field(message, 'transport', 'stdio'):
            if field(message, 'initialized', 'true') and field(message, 'next', 'connected'):
                return 'local_backend_connected'
            if field(message, 'initialized', 'false'):
                return 'local_backend_not_initialized'
    if logger == 'electron-message-handler':
        if message.startswith('sa_server_request_failed ') and field(message, 'errorCode', 'ERR_CONNECTION_TIMED_OUT'):
            return 'desktop_request_timeout'
        if message.startswith('Statsig: error while bootstrapping post-login client') and 'ERR_CONNECTION_TIMED_OUT' in message:
            return 'feature_bootstrap_timeout'
    if logger is None and message.startswith('windows_core_runtime_component_resolved ') and field(message, 'component', 'cua-swift-helper'):
        return 'computer_use_component_resolved_only'
    return None


def empty_report():
    return {
        'backend': {'status': 'unknown', 'pid_correlated': False},
        'network': {'status': 'not_checked', 'request_timeout_observed': False, 'feature_bootstrap_timeout_observed': False},
        'computer_use': {'status': 'unknown', 'reason': 'no_supported_capability_readiness_event', 'component_resolved': False, 'computer_action_performed': False},
        'evidence_counts': {}, 'bytes_read': 0, 'scan_limited': False,
    }


def observe(cursor, *, expected_pid, not_before, report=None):
    report = empty_report() if report is None else report
    if cursor['root'] is None:
        report['computer_use']['reason'] = 'desktop_log_directory_not_provided'
        return report
    files, limited = list_logs(cursor['root'])
    if report['network']['status'] == 'not_checked':
        report['network']['status'] = 'not_observed_in_window'
    report['scan_limited'] = report['scan_limited'] or limited or cursor['limited']
    for path, info in files:
        if cursor['bytes_read'] >= MAX_BYTES:
            report['scan_limited'] = True
            break
        key = str(path)
        identity = (info.st_dev, info.st_ino)
        state = cursor['files'].get(key)
        if state is None or state['identity'] != identity or info.st_size < state['offset']:
            state = {'identity': identity, 'offset': 0, 'carry': b''}
            cursor['files'][key] = state
        count = min(MAX_FILE_BYTES, MAX_BYTES - cursor['bytes_read'], max(0, info.st_size - state['offset']))
        if not count:
            continue
        safe_path(path)
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != identity:
                report['scan_limited'] = True
                continue
            stream.seek(state['offset'])
            chunk = stream.read(count)
        state['offset'] += len(chunk)
        cursor['bytes_read'] += len(chunk)
        parts = (state['carry'] + chunk).split(b'\n')
        state['carry'] = parts.pop()
        if len(state['carry']) > MAX_LINE:
            state['carry'] = b''
            report['scan_limited'] = True
        pid_match = PID_FILE.fullmatch(path.name)
        source_pid = int(pid_match.group(1)) if pid_match else None
        for raw in parts:
            if len(raw) > MAX_LINE:
                report['scan_limited'] = True
                continue
            event = classify(raw.decode('utf-8', errors='replace').rstrip('\r'), not_before, expected_pid, source_pid)
            if event is None:
                continue
            report['evidence_counts'][event] = report['evidence_counts'].get(event, 0) + 1
            timestamp = LINE.fullmatch(raw.decode('utf-8', errors='replace').rstrip('\r')).group(1)
            event_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
            if event in ('local_backend_handshake_success', 'local_backend_connected', 'local_backend_not_initialized'):
                if event_at >= cursor.get('backend_at', -1):
                    cursor['backend_at'] = event_at
                    status = 'not_initialized_reported' if event == 'local_backend_not_initialized' else 'ready_reported'
                    report['backend'] = {'status': status, 'pid_correlated': True}
            elif event == 'desktop_request_timeout':
                report['network']['status'] = 'timeout_observed'
                report['network']['request_timeout_observed'] = True
            elif event == 'feature_bootstrap_timeout':
                report['network']['status'] = 'timeout_observed'
                report['network']['feature_bootstrap_timeout_observed'] = True
            elif event == 'computer_use_component_resolved_only':
                report['computer_use']['component_resolved'] = True
    report['bytes_read'] = cursor['bytes_read']
    return report


def watch(cursor, *, expected_pid, not_before, timeout=60, interval=0.5):
    if type(expected_pid) is not int or expected_pid <= 0:
        raise ValueError('A verified newly started desktop PID is required.')
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 <= timeout <= 120:
        raise ValueError('Readiness observation timeout must be 0 through 120 seconds.')
    if not isinstance(interval, (int, float)) or isinstance(interval, bool) or not 0 < interval <= 5:
        raise ValueError('Invalid readiness observation interval.')
    if (not isinstance(not_before, (int, float)) or isinstance(not_before, bool)
            or not math.isfinite(not_before) or not_before < cursor['captured_at']):
        raise ValueError('Startup timestamp must be finite and not precede the captured log baseline.')
    began = time.monotonic()
    deadline = began + timeout
    report = empty_report()
    while True:
        report = observe(cursor, expected_pid=expected_pid, not_before=not_before, report=report)
        if (cursor['root'] is None or report['network']['status'] == 'timeout_observed'
                or cursor['bytes_read'] >= MAX_BYTES or time.monotonic() >= deadline):
            break
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    report['observation_seconds'] = round(time.monotonic() - began, 3)
    report['computer_use']['note'] = 'No supported Computer Use readiness event is known for this desktop log format. Verify capability in the application; no computer action was attempted.'
    return report
