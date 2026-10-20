"""Offline lifecycle tests. No real processes, windows, state, listener or ledger."""
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest import mock

ASSET = Path(__file__).resolve().parents[1] / "skills/clash-codex-optimizer/assets/launch_codex.py"
SPEC = importlib.util.spec_from_file_location("desktop_lifecycle_launcher", ASSET)
L = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(L)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.config = {"kind": "electron", "codex_exe": str(ASSET.parent / "Codex.exe"),
                       "proxy_url": "http://127.0.0.1:17891"}
        self.path = ASSET.parent / "synthetic-state/config.json"
        self.token = "a" * 32
        self.clock = 0.0
        self.parent = dict(os.environ)
        self.patch("os", mock.Mock(wraps=os, name="windows_os"))
        L.os.name = "nt"
        L.os.environ = os.environ
        self.patch("safe_path", side_effect=lambda p: Path(p))
        self.load = self.patch("load_owned_config", return_value=self.config)
        self.listener = self.patch("check_listener")
        self.inventory = self.patch("process_inventory", return_value=[])
        self.windows = self.patch("desktop_windows", return_value=[101])
        self.close = self.patch("post_close")
        self.claim = self.patch("claim_action")
        self.old_probe = self.patch("desktop_running", return_value=False)
        self.run = mock.patch.object(L.subprocess, "run").start()
        self.addCleanup(mock.patch.stopall)
        self.child = mock.Mock(pid=30)
        self.child.poll.return_value = None
        self.popen = mock.patch.object(L.subprocess, "Popen", return_value=self.child).start()
        mock.patch.object(L.time, "monotonic", side_effect=lambda: self.clock).start()
        mock.patch.object(L.time, "time", return_value=1234567890.25).start()
        mock.patch.object(L.time, "sleep", side_effect=self.sleep).start()

    def patch(self, name, *args, **kwargs):
        patch = mock.patch.object(L, name, *args, **kwargs)
        result = patch.start()
        self.addCleanup(patch.stop)
        return result

    def sleep(self, delay):
        self.clock += delay

    def row(self, pid=10, ppid=1, created="birth-10", path=None):
        return {"Name": "Codex.exe", "ExecutablePath": path or self.config["codex_exe"],
                "ProcessId": pid, "ParentProcessId": ppid, "Created": created}

    def repair(self, **kw):
        before = self.popen.call_count
        result = L.repair_desktop(self.path, self.token, close_timeout=.3, start_timeout=.3, **kw)
        json.dumps(result)
        self.assertEqual(os.environ, self.parent)
        self.assertLessEqual(self.popen.call_count - before, 1)
        self.assertFalse(result["gui_ready"])
        self.assertFalse(result["workspace_ready"])
        self.assertFalse(result["computer_use_ready"])
        if result["status"] != "started":
            self.assertIsNone(result["pid"])
        return result

    def sequence(self, *rows):
        iterator = iter(rows)
        last = rows[-1]
        self.inventory.side_effect = lambda: next(iterator, last)

    def test_import_and_command_build_have_no_lifecycle_side_effects(self):
        L.build_command(self.config)
        for call in (self.inventory, self.windows, self.close, self.claim, self.popen):
            call.assert_not_called()

    def test_foreground_default_remains_run_not_popen(self):
        self.run.return_value.returncode = 7
        self.assertEqual(L.launch(self.path), 7)
        self.old_probe.assert_called_once_with(self.config["codex_exe"])
        self.assertEqual(self.run.call_args.args[0], L.build_command(self.config))
        self.assertFalse(self.run.call_args.kwargs["shell"])
        self.popen.assert_not_called()
        self.claim.assert_not_called()

    def test_foreground_cli_args_and_desktop_override_rules(self):
        self.config["kind"] = "cli"
        L.launch(self.path, ["--proxy-custom", "hello"])
        self.assertEqual(self.run.call_args.args[0][-2:], ["--proxy-custom", "hello"])
        self.old_probe.assert_not_called()
        self.config["kind"] = "electron"
        for arg in ("--proxy-server=x", "--NO-PROXY", "--host-resolver-rules=x", "bad\x00arg"):
            with self.assertRaises(ValueError):
                L.build_command(self.config, [arg])

    def test_no_desktop_one_start_shared_flags_environment(self):
        self.sequence([], [], [], [self.row(30)], [self.row(30)])
        result = self.repair()
        self.assertEqual(result["status"], "started")
        self.assertEqual(result["pid"], 30)
        self.assertEqual(result["started_at"], 1234567890.25)
        self.assertIsInstance(result["started_at"], float)
        self.assertFalse(result["close_attempted"])
        self.close.assert_not_called()
        args, kwargs = self.popen.call_args
        self.assertEqual(args, (L.build_command(self.config),))
        self.assertEqual(kwargs, {"shell": False, "env": L.child_environment(os.environ, self.config["proxy_url"]),
                                  "stdin": L.subprocess.DEVNULL, "stdout": L.subprocess.DEVNULL, "stderr": L.subprocess.DEVNULL})
        self.assertIn("--proxy-bypass-list=localhost;127.0.0.1;[::1]", args[0])
        self.child.wait.assert_not_called()
        self.child.kill.assert_not_called()
        self.child.terminate.assert_not_called()

    def test_close_root_only_waits_for_all_gui_exe_children(self):
        original = [self.row(), self.row(11, 10, "child")]
        self.sequence(original, original, original, [original[1]], [], [], [self.row(30)], [self.row(30)])
        result = self.repair()
        self.assertEqual(result["status"], "started")
        self.assertTrue(result["close_attempted"])
        self.windows.assert_called_once_with(10)
        self.close.assert_called_once_with(101, 10)
        self.assertGreater(self.clock, 0)

    def test_preflight_unknown_ambiguous_and_wrong_path(self):
        for rows in ([self.row(), self.row(20)], [self.row(path=str(ASSET.parent / "other/Codex.exe"))],
                     [dict(self.row(), ExecutablePath=None)], [dict(self.row(), Created=None)],
                     [dict(self.row(), ParentProcessId=None)]):
            with self.subTest(rows=rows):
                self.inventory.return_value = rows
                self.assertEqual(self.repair()["status"], "preflight_failed")
                self.claim.assert_not_called()
                self.close.assert_not_called()
                self.popen.assert_not_called()

    def test_no_window_or_tray_only_preserves_work_without_claim(self):
        self.inventory.return_value = [self.row()]
        for windows in ([], list(range(L.MAX_WINDOWS + 1)), [101, 101]):
            self.windows.return_value = windows
            self.assertEqual(self.repair()["status"], "no_safe_windows")
        self.claim.assert_not_called()
        self.close.assert_not_called()
        self.popen.assert_not_called()

    def test_pid_reuse_before_close_and_during_wait(self):
        original = [self.row()]
        reused = [self.row(created="reused")]
        for sequence in ((original, reused), (original, original, reused),
                         (original, original, original, reused)):
            self.close.reset_mock()
            self.sequence(*sequence)
            self.assertEqual(self.repair()["status"], "identity_changed")
            self.assertLessEqual(self.close.call_count, 1)
            self.popen.assert_not_called()

    def test_competing_instance_during_close_or_before_start(self):
        original = [self.row()]
        for sequence in ((original, original, original, original + [self.row(20)]),
                         (original, original, original, [], [self.row(20)]),
                         ([], [], [self.row(20)])):
            self.sequence(*sequence)
            self.assertEqual(self.repair()["status"], "identity_changed")
            self.popen.assert_not_called()

    def test_save_prompt_close_timeout_never_reposts_or_starts(self):
        self.inventory.return_value = [self.row()]
        result = self.repair()
        self.assertEqual(result["status"], "close_timeout")
        self.assertTrue(result["close_attempted"])
        self.close.assert_called_once_with(101, 10)
        self.popen.assert_not_called()
        self.assertGreaterEqual(self.clock, .3)

    def test_close_refusal_and_inaccessible_recheck_consume_token(self):
        self.inventory.return_value = [self.row()]
        self.close.side_effect = OSError("synthetic refusal")
        self.assertEqual(self.repair()["status"], "close_refused")
        self.claim.assert_called_once()
        self.popen.assert_not_called()
        self.close.side_effect = None
        self.sequence([self.row()], [dict(self.row(), ExecutablePath=None)])
        self.assertEqual(self.repair()["status"], "identity_changed")
        self.popen.assert_not_called()

    def test_each_window_has_immediate_identity_recheck(self):
        self.windows.return_value = [101, 102]
        original = [self.row()]
        self.sequence(original, original, original, [self.row(created="replacement")])
        self.assertEqual(self.repair()["status"], "identity_changed")
        self.close.assert_called_once_with(101, 10)

    def test_start_early_exit_handoff_timeout_unknown_and_no_respawn(self):
        for rows, exited, status in (([], 1, "start_early_exit"), ([self.row(40)], 0, "start_handoff"),
                                     ([], None, "start_timeout")):
            with self.subTest(status=status):
                self.popen.reset_mock()
                self.child.poll.return_value = exited
                self.sequence([], [], [], rows)
                self.assertEqual(self.repair()["status"], status)
                self.popen.assert_called_once()
        self.sequence([], [], [], [dict(self.row(30), Created=None)])
        self.assertEqual(self.repair()["status"], "start_unknown")
        self.child.wait.assert_not_called()
        self.child.kill.assert_not_called()
        self.child.terminate.assert_not_called()

    def test_launch_identity_confirmation_and_exit_handoff(self):
        self.sequence([], [], [], [self.row(30)], [self.row(30, created="reused")])
        self.assertEqual(self.repair()["status"], "start_identity_changed")
        self.sequence([], [], [], [self.row(30)], [self.row(40)])
        self.child.poll.side_effect = [None, 0]
        self.assertEqual(self.repair()["status"], "start_handoff")

    def test_preflight_validation_and_owl_remain_unverified(self):
        for value in (True, 0, -1, float("inf"), float("nan"), 301, "20"):
            self.assertEqual(L.repair_desktop(self.path, self.token, value)["status"], "preflight_failed")
        for token in (None, "x" * 32, "a" * 31, "../" + "a" * 32):
            self.assertEqual(L.repair_desktop(self.path, token)["status"], "preflight_failed")
        self.claim.assert_not_called()
        self.config["kind"] = "cli"
        self.assertEqual(self.repair()["status"], "preflight_failed")
        self.config["kind"] = "owl"
        self.sequence([], [], [], [self.row(30)], [self.row(30)])
        self.assertEqual(self.repair()["compatibility"], "unverified-owl-proxy-flag")

    def test_timeout_consumes_token_and_cannot_spawn_again(self):
        claimed = set()
        def claim(path, token):
            key = (Path(path).parent.parent, token.lower())
            if key in claimed:
                raise FileExistsError()
            claimed.add(key)
        self.claim.side_effect = claim
        self.assertEqual(self.repair()["status"], "start_timeout")
        self.popen.assert_called_once()
        self.path = self.path.parent.parent / "other-state/config.json"
        self.assertEqual(self.repair()["status"], "action_claim_failed")
        self.popen.assert_called_once()
        self.close.assert_not_called()

    def test_action_replay_does_not_close_or_launch(self):
        self.inventory.return_value = [self.row()]
        self.claim.side_effect = FileExistsError("already consumed")
        self.assertEqual(self.repair()["status"], "action_claim_failed")
        self.close.assert_not_called()
        self.popen.assert_not_called()


class Win32AdapterTests(unittest.TestCase):
    def test_window_adapter_filters_root_and_only_posts_wm_close(self):
        import ctypes
        user32 = mock.Mock()
        owners = {101: 10, 102: 11, 103: 10}
        def owner(hwnd, pointer):
            pointer._obj.value = owners.get(hwnd, 0)
            return 1
        def enumerate_windows(callback, data):
            for hwnd in owners:
                if not callback(hwnd, data):
                    return 0
            return 1
        user32.GetWindowThreadProcessId.side_effect = owner
        user32.IsWindowVisible.side_effect = lambda hwnd: hwnd != 103
        user32.EnumWindows.side_effect = enumerate_windows
        user32.PostMessageW.return_value = 1
        callback_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        with mock.patch.object(ctypes, "WinDLL", return_value=user32, create=True), \
             mock.patch.object(ctypes, "WINFUNCTYPE", callback_type, create=True):
            self.assertEqual(L.desktop_windows(10), [101])
            L.post_close(101, 10)
            user32.PostMessageW.assert_called_once_with(101, 0x0010, 0, 0)
            with self.assertRaises(ValueError):
                L.post_close(102, 10)
            with self.assertRaises(ValueError):
                L.post_close(103, 10)
            user32.PostMessageW.assert_called_once()
            user32.PostMessageW.return_value = 0
            with self.assertRaises(ValueError):
                L.post_close(101, 10)

    def test_inventory_uses_fixed_readonly_fields_not_command_lines(self):
        native_name = os.name
        windows_os = mock.Mock(wraps=os)
        windows_os.name = "nt"
        with mock.patch.object(L, "safe_path", return_value=mock.Mock(is_file=lambda: True)), \
             mock.patch.object(L, "os", windows_os), \
             mock.patch.object(L.subprocess, "run", return_value=mock.Mock(stdout="[]")) as run:
            self.assertEqual(L.process_inventory(), [])
            self.assertEqual(os.name, native_name)
            command = run.call_args.args[0][-1]
            self.assertIn("Get-CimInstance Win32_Process", command)
            self.assertIn("ParentProcessId", command)
            self.assertIn("CreationDate", command)
            for forbidden in ("CommandLine", "Stop-Process", "Environment", "Invoke-Expression"):
                self.assertNotIn(forbidden, command)
            self.assertFalse(run.call_args.kwargs["shell"])


class LedgerTests(unittest.TestCase):
    def test_exclusive_shared_parent_token_modes_and_generic_record(self):
        # Filesystem is entirely mocked; test never creates a real ledger.
        root = ASSET.parent
        paths = []
        records = []
        claimed = set()
        def exclusive(path, flags, mode):
            paths.append((path, flags, mode))
            if path in claimed:
                raise FileExistsError()
            claimed.add(path)
            return 123
        class Stream(io.StringIO):
            def fileno(self):
                return 123
            def close(self):
                records.append(self.getvalue())
                super().close()
        with mock.patch.object(L, "safe_path", side_effect=lambda p: Path(p)), \
             mock.patch.object(Path, "mkdir") as mkdir, \
             mock.patch.object(Path, "is_dir", return_value=True), \
             mock.patch.object(L.os, "open", side_effect=exclusive), \
             mock.patch.object(L.os, "fdopen", side_effect=lambda *a, **k: Stream()), \
             mock.patch.object(L.os, "fsync") as synced:
            # LifecycleTests' adapter patch is scoped; use real implementation.
            L.claim_action(root / "state-a/config.json", "A" * 32)
            with self.assertRaises(FileExistsError):
                L.claim_action(root / "state-b/config.json", "a" * 32)
            self.assertEqual(paths[0][0], root / ".clash-codex-actions" / ("a" * 32 + ".json"))
            self.assertEqual(paths[0][2], 0o600)
            self.assertTrue(paths[0][1] & os.O_EXCL)
            self.assertEqual(mkdir.call_args.kwargs, {"mode": 0o700})
            self.assertEqual(json.loads(records[0]), {"owner": L.OWNER, "action": "repair-desktop"})
            synced.assert_called_once_with(123)

    def test_ledger_link_refused_before_open(self):
        with mock.patch.object(L, "safe_path", side_effect=ValueError("reparse")), \
             mock.patch.object(L.os, "open") as opened:
            with self.assertRaises(ValueError):
                L.claim_action(ASSET.parent / "state/config.json", "a" * 32)
            opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
