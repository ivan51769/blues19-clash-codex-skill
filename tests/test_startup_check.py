"""Synthetic startup logs only; never read real app logs or start processes."""
import importlib.util
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/clash-codex-optimizer/scripts/startup_check.py'
spec = importlib.util.spec_from_file_location('startup_check_test', SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def line(timestamp, message, logger='AppServerConnection', severity='info'):
    stamp = datetime.fromtimestamp(timestamp + 0.001, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    return stamp + ' ' + severity + ' ' + ('[' + logger + '] ' if logger else '') + message + '\n'


def filename(pid, suffix=0):
    return f'codex-desktop-{uuid.UUID(int=0)}-{pid}-t0-i1-010101-{suffix}.log'


class StartupCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pid = 12345
        self.file = self.root / filename(self.pid)
        self.file.write_bytes(b'')
        self.cursor = check.capture(self.root)
        self.started = self.cursor['captured_at'] + 0.01

    def append(self, content, file=None):
        with (self.file if file is None else file).open('ab') as stream:
            stream.write(content.encode('utf-8'))

    def report(self):
        return check.watch(self.cursor, expected_pid=self.pid, not_before=self.started, timeout=0)

    def test_capture_is_read_only_and_historical_readiness_is_ignored(self):
        old = line(time.time() - 60, 'initialize_handshake_result outcome=success transportKind=stdio')
        self.file.write_text(old, encoding='utf-8')
        before = self.file.read_bytes()
        self.cursor = check.capture(self.root)
        self.started = self.cursor['captured_at'] + 0.01
        result = self.report()
        self.assertEqual(result['backend']['status'], 'unknown')
        self.assertEqual(result['bytes_read'], 0)
        self.assertEqual(self.file.read_bytes(), before)

    def test_fresh_local_backend_is_not_computer_use_ready(self):
        self.append(line(self.started, 'initialize_handshake_result outcome=success durationMs=12 transportKind=stdio'))
        result = self.report()
        self.assertEqual(result['backend']['status'], 'ready_reported')
        self.assertTrue(result['backend']['pid_correlated'])
        self.assertEqual(result['computer_use']['status'], 'unknown')

    def test_connected_marker_requires_local_stdio(self):
        for message in ['app_server_connection.state_changed hostId=remote initialized=true next=connected transport=stdio',
                        'app_server_connection.state_changed hostId=local initialized=true next=connected transport=websocket']:
            self.append(line(self.started, message))
        self.assertEqual(self.report()['backend']['status'], 'unknown')
        self.append(line(self.started + 0.1, 'app_server_connection.state_changed hostId="local" initialized=true next=connected transport=stdio'))
        self.assertEqual(self.report()['backend']['status'], 'ready_reported')

    def test_wrong_pid_and_unrecognized_file_name_are_unattributed(self):
        for file in [self.root / filename(self.pid + 1), self.root / 'generic.log']:
            file.write_text(line(self.started, 'initialize_handshake_result outcome=success transportKind=stdio'), encoding='utf-8')
        self.assertEqual(self.report()['backend']['status'], 'unknown')

    def test_old_timestamp_appended_after_baseline_is_not_fresh(self):
        self.append(line(self.started - 120, 'initialize_handshake_result outcome=success transportKind=stdio'))
        self.assertEqual(self.report()['backend']['status'], 'unknown')

    def test_component_resolution_and_generic_plugin_skip_do_not_imply_ready_or_skip(self):
        self.append(line(self.started, 'windows_core_runtime_component_resolved component=cua-swift-helper source=copied', logger=None))
        self.append(line(self.started, 'bundled_plugins_reconcile_skipped_features_unavailable reason=focus', logger='bundled-plugins'))
        self.append(line(self.started, 'primary_runtime_selection reason=gate-disabled', logger='install-primary-runtime'))
        result = self.report()
        self.assertTrue(result['computer_use']['component_resolved'])
        self.assertEqual(result['computer_use']['status'], 'unknown')

    def test_network_timeout_is_separate_and_output_is_sanitized(self):
        self.append(line(self.started, 'sa_server_request_failed errorCode=ERR_CONNECTION_TIMED_OUT status=500 token=synthetic-private url=https://example.invalid/?secret=synthetic-private', logger='electron-message-handler', severity='warning'))
        result = self.report()
        self.assertTrue(result['network']['request_timeout_observed'])
        self.assertEqual(result['computer_use']['status'], 'unknown')
        output = json.dumps(result)
        for value in ('synthetic-private', 'example.invalid', str(self.root), 'token='):
            self.assertNotIn(value, output)

    def test_feature_bootstrap_timeout_is_not_capability_failure(self):
        self.append(line(self.started, 'Statsig: error while bootstrapping post-login client ERR_CONNECTION_TIMED_OUT', logger='electron-message-handler', severity='error'))
        result = self.report()
        self.assertTrue(result['network']['feature_bootstrap_timeout_observed'])
        self.assertEqual(result['computer_use']['status'], 'unknown')

    def test_api_status_401_or_500_and_arbitrary_ready_text_are_not_proof(self):
        for message in ['Computer Use initialization succeeded', 'HTTP 401', 'status=500', 'response_routed readiness=true']:
            self.append(line(self.started, message, logger='electron-message-handler'))
        result = self.report()
        self.assertEqual(result['backend']['status'], 'unknown')
        self.assertEqual(result['computer_use']['status'], 'unknown')
        self.assertFalse(result['network']['request_timeout_observed'])

    def test_rotation_and_truncation_still_require_fresh_timestamps(self):
        old = line(self.started - 10, 'initialize_handshake_result outcome=success transportKind=stdio')
        self.file.write_text(old, encoding='utf-8')
        self.cursor = check.capture(self.root)
        self.started = self.cursor['captured_at'] + 0.01
        self.file.unlink()
        self.file.write_text(old, encoding='utf-8')
        self.assertEqual(self.report()['backend']['status'], 'unknown')
        self.file.write_text(line(self.started, 'initialize_handshake_result outcome=success transportKind=stdio'), encoding='utf-8')
        # Force a true truncation before the append observation.
        self.file.write_bytes(b'')
        check.observe(self.cursor, expected_pid=self.pid, not_before=self.started)
        self.append(line(self.started, 'initialize_handshake_result outcome=success transportKind=stdio'))
        self.assertEqual(self.report()['backend']['status'], 'ready_reported')

    def test_latest_backend_event_wins_across_files_and_polls(self):
        self.append(line(self.started + 0.2, 'app_server_connection.state_changed hostId=local initialized=true next=connected transport=stdio'))
        result = self.report()
        self.assertEqual(result['backend']['status'], 'ready_reported')
        older = self.root / filename(self.pid, 1)
        older.write_text(line(self.started + 0.1, 'app_server_connection.state_changed hostId=local initialized=false next=connecting transport=stdio'), encoding='utf-8')
        result = check.observe(self.cursor, expected_pid=self.pid, not_before=self.started, report=result)
        self.assertEqual(result['backend']['status'], 'ready_reported')

    def test_partial_lines_are_not_evidence_until_complete(self):
        content = line(self.started, 'initialize_handshake_result outcome=success transportKind=stdio')
        self.append(content[:-1])
        self.assertEqual(self.report()['backend']['status'], 'unknown')
        self.append('\n')
        self.assertEqual(self.report()['backend']['status'], 'ready_reported')

    def test_bounds_no_log_dir_and_invalid_inputs(self):
        self.append('x' * (check.MAX_LINE + 10) + '\n')
        self.assertTrue(self.report()['scan_limited'])
        result = check.watch(check.capture(None), expected_pid=self.pid, not_before=time.time(), timeout=0)
        self.assertEqual(result['computer_use']['status'], 'unknown')
        for timeout in (-1, 121, float('nan'), True):
            with self.assertRaises(ValueError):
                check.watch(self.cursor, expected_pid=self.pid, not_before=self.started, timeout=timeout)
        for pid in (0, True, '123'):
            with self.assertRaises(ValueError):
                check.watch(self.cursor, expected_pid=pid, not_before=self.started, timeout=0)
        with self.assertRaises(ValueError):
            check.watch(self.cursor, expected_pid=self.pid, not_before=float('nan'), timeout=0)


if __name__ == '__main__':
    unittest.main()
