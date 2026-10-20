"""Synthetic, offline tests: never inspect real settings or invoke installed Codex."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_proxy", ROOT / "skills" / "clash-codex-optimizer" / "scripts" / "codex_proxy.py")
proxy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proxy)
R = proxy._runtime


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clash = self.root / "clash"
        self.clash.mkdir()
        self.config = self.clash / "config.yaml"
        self.config.write_text("mixed-port: 17891\nport: 17890\nmode: rule\n", encoding="utf-8")
        self.exe = self.root / ("codex.exe" if os.name == "nt" else "codex")
        self.exe.write_bytes(b"synthetic executable; never run")
        self.exe.chmod(0o700)
        self.state = self.root / "state"

    def plan(self, **kw):
        args = dict(clash_dir=self.clash, codex_exe=self.exe, kind="cli", state_dir=self.state, check_listener=False)
        args.update(kw)
        return proxy.prepare(**args)

    def installed(self, **kw):
        return proxy.install(self.plan(**kw), apply=True)

    def test_windows_default_avoids_packaged_host_localappdata_redirection(self):
        windows = mock.Mock(wraps=os)
        windows.name = 'nt'
        with mock.patch.object(proxy, 'os', windows), mock.patch.object(Path, 'home', return_value=self.root):
            self.assertEqual(proxy.default_state_dir(), self.root / '.clash-codex-optimizer')
        self.assertFalse((self.root / '.clash-codex-optimizer').exists())

    def test_preview_no_writes_and_shape(self):
        plan = self.plan()
        result = proxy.install(plan)
        self.assertFalse(result["changed"])
        self.assertFalse(self.state.exists())
        data = json.loads(plan["files"]["config.json"])
        self.assertEqual(set(data), {"owner", "version", "codex_exe", "kind", "proxy_url", "python_exe"})
        self.assertEqual(data["proxy_url"], "http://127.0.0.1:17891")
        self.assertEqual(plan["files"]["launch_codex.py"].encode(), proxy.ASSET.read_bytes())

    def test_parser_priority_and_http_fallback(self):
        for text, expected in [("mode: global\nport: 10123\n", 10123),
                               ("mixed-port: 0\nport: 10124 # comment\n", 10124),
                               ("socks-port: 10125\nport: 10126\nexternal-controller: 127.0.0.1:9090\n", 10126),
                               ("---\nprofiles:\n  mixed-port: 10128\nport: 10129\n", 10129)]:
            with self.subTest(text=text):
                self.config.write_text(text)
                self.assertEqual(proxy.detect_proxy_port(self.clash), expected)

    def test_parser_rejects_ambiguous_values(self):
        for text in ["mixed-port: 1\nmixed-port: 2\n", "mixed-port: [123]\n", "mixed-port:\n  value: 123\n",
                     "mixed-port: '123'\n", "mixed-port: &p 123\n", "mixed-port: *p\n", "mixed-port: true\n",
                     "port: 65536\n", "port: -1\n", "socks-port: 123\n", "port: 0\n", '"port": 123\n',
                     "port: 123\n---\nport: 124\n", "port: 123\nmode: rule\nmode: global\n",
                     "{port: 123}\n", "port: 123\n<<: *defaults\n"]:
            with self.subTest(text=text):
                self.config.write_text(text)
                with self.assertRaises(ValueError):
                    proxy.detect_proxy_port(self.clash)

    def test_explicit_port_does_not_read_config(self):
        self.config.unlink()
        self.assertIn("http://127.0.0.1:12345", self.plan(proxy_port=12345)["files"]["config.json"])
        for port in [True, 0, 65536, "1;whoami", 1.2, " 123"]:
            with self.assertRaises(ValueError):
                self.plan(proxy_port=port)

    def test_listener_offline(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen()
            self.plan(proxy_port=port, check_listener=True)
        with self.assertRaisesRegex(ValueError, "No TCP listener"):
            self.plan(proxy_port=port, check_listener=True)
        self.assertFalse(self.state.exists())

    def test_environment_is_process_only(self):
        parent = {"HTTP_PROXY": "previous", "No_Proxy": "*", "TOKEN": "synthetic-only", "PATH": "example"}
        saved = dict(parent)
        env = R["child_environment"](parent, "http://127.0.0.1:12345")
        self.assertEqual(parent, saved)
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            self.assertEqual(env[key], "http://127.0.0.1:12345")
        self.assertEqual(env["NO_PROXY"], "localhost,127.0.0.1,::1")
        self.assertEqual(env["no_proxy"], env["NO_PROXY"])
        self.assertNotIn("No_Proxy", env)

    def test_install_restore_and_stacked_backups(self):
        first = self.installed()
        original = (self.state / "config.json").read_bytes()
        second = self.installed(proxy_port=12345)
        self.assertNotEqual((self.state / "config.json").read_bytes(), original)
        self.assertFalse(proxy.restore(self.state, second["manifest"])["changed"])
        proxy.restore(self.state, second["manifest"], apply=True)
        self.assertEqual((self.state / "config.json").read_bytes(), original)
        proxy.restore(self.state, first["manifest"], apply=True)
        self.assertFalse(self.state.exists())

    def test_frozen_manifest_refuses_later_generation(self):
        first = self.installed()
        self.assertIsInstance(first["manifest_data"], dict)
        second = self.installed(proxy_port=12345)
        with self.assertRaisesRegex(ValueError, "does not match"):
            proxy.restore(self.state, first["manifest_data"], apply=True)
        proxy.restore(self.state, second["manifest_data"], apply=True)
        proxy.restore(self.state, first["manifest_data"], apply=True)
        self.assertFalse(self.state.exists())

    def test_restore_partial_backup_cleanup_failure_compensates(self):
        original_unlink = Path.unlink
        for stacked in (False, True):
            if self.state.exists():
                proxy.restore(self.state, self.state / "manifest.json", apply=True)
            result = self.installed()
            if stacked:
                result = self.installed(proxy_port=12345)
            before = proxy._tree_hash(self.state)
            failed = [False]
            def partial_unlink(path, *args, **kwargs):
                if path.name == "snapshot.json" and not failed[0]:
                    failed[0] = True
                    original_unlink(path, *args, **kwargs)
                    raise OSError("synthetic partial backup cleanup failure")
                return original_unlink(path, *args, **kwargs)
            with mock.patch.object(Path, "unlink", partial_unlink):
                with self.assertRaises(OSError):
                    proxy.restore(self.state, result["manifest_data"], apply=True)
            self.assertTrue(failed[0])
            self.assertEqual(proxy._tree_hash(self.state), before)
            proxy._managed(self.state)

    def test_restore_directory_cleanup_preserves_concurrent_user_file(self):
        result = self.installed()
        before = proxy._tree_hash(self.state)
        original_rmdir = Path.rmdir
        custom = self.state / "concurrent-user.txt"
        def concurrent_rmdir(path, *args, **kwargs):
            if path == self.state:
                custom.write_text("preserve user data")
            return original_rmdir(path, *args, **kwargs)
        with mock.patch.object(Path, "rmdir", concurrent_rmdir):
            with self.assertRaises(OSError):
                proxy.restore(self.state, result["manifest_data"], apply=True)
        self.assertEqual(custom.read_text(), "preserve user data")
        custom.unlink()
        self.assertEqual(proxy._tree_hash(self.state), before)
        proxy._managed(self.state)

    def test_fresh_install_exclusive_mkdir_race_preserves_other_directory(self):
        plan = self.plan()
        original_mkdir = Path.mkdir
        custom = self.state / "concurrent-user.txt"
        raced = [False]
        def concurrent_mkdir(path, *args, **kwargs):
            if path == self.state and not raced[0]:
                raced[0] = True
                original_mkdir(path)
                custom.write_text("not installer owned")
            return original_mkdir(path, *args, **kwargs)
        with mock.patch.object(Path, "mkdir", concurrent_mkdir):
            with self.assertRaises(FileExistsError):
                proxy.install(plan, apply=True)
        self.assertEqual(custom.read_text(), "not installer owned")
        self.assertEqual({p.name for p in self.state.iterdir()}, {custom.name})

    def test_failed_fresh_install_refuses_cleanup_of_concurrent_files(self):
        plan = self.plan()
        original_atomic = proxy._atomic
        custom = self.state / "concurrent-user.txt"
        calls = [0]
        def concurrent_failure(path, data, mode=0o600):
            calls[0] += 1
            if calls[0] == 3:
                custom.write_text("must survive")
                raise OSError("synthetic apply failure")
            return original_atomic(path, data, mode)
        with mock.patch.object(proxy, "_atomic", side_effect=concurrent_failure):
            with self.assertRaisesRegex(ValueError, "unsafe rollback cleanup"):
                proxy.install(plan, apply=True)
        self.assertEqual(custom.read_text(), "must survive")

    def test_refuse_custom_or_empty_directory(self):
        self.state.mkdir()
        with self.assertRaises((ValueError, OSError)):
            self.plan()
        (self.state / "custom.txt").write_text("do not alter")
        with self.assertRaises((ValueError, OSError)):
            self.plan()
        self.assertEqual((self.state / "custom.txt").read_text(), "do not alter")

    def test_refuse_user_edits_and_extras(self):
        result = self.installed()
        original = (self.state / "config.json").read_bytes()
        (self.state / "config.json").write_bytes(original + b" ")
        with self.assertRaises(ValueError):
            proxy.restore(self.state, result["manifest"], apply=True)
        with self.assertRaises(ValueError):
            self.plan()
        (self.state / "config.json").write_bytes(original)
        (self.state / "custom.txt").write_text("custom")
        with self.assertRaises(ValueError):
            proxy.restore(self.state, result["manifest"], apply=True)

    def test_refuse_backup_edits(self):
        result = self.installed()
        backup = next((self.state / "backups").glob("*/snapshot.json"))
        backup.write_text("{} ")
        with self.assertRaises(ValueError):
            proxy.restore(self.state, result["manifest"], apply=True)

    def test_plan_staleness_and_tampering(self):
        plan = self.plan()
        self.installed()
        with self.assertRaises(ValueError):
            proxy.install(plan, apply=True)
        plan = self.plan()
        plan["files"]["launch_codex.py"] += "\n# tamper\n"
        with self.assertRaises(ValueError):
            proxy.install(plan, apply=True)

    def test_partial_failure_rolls_back_new_and_existing(self):
        original_atomic = proxy._atomic
        for existing in (False, True):
            if existing:
                self.installed()
            before = proxy._tree_hash(self.state)
            plan = self.plan(proxy_port=12346)
            calls = [0]
            def fail_once(path, data, mode=0o600):
                calls[0] += 1
                if calls[0] == 3:
                    raise OSError("synthetic write failure")
                return original_atomic(path, data, mode)
            with mock.patch.object(proxy, "_atomic", side_effect=fail_once):
                with self.assertRaises(OSError):
                    proxy.install(plan, apply=True)
            self.assertEqual(proxy._tree_hash(self.state), before)

    def test_dedicated_state_and_no_shell_targets(self):
        for target in (self.clash / "state", ROOT / "synthetic-state"):
            with self.assertRaises(ValueError):
                self.plan(state_dir=target)
        for suffix in (".cmd", ".bat"):
            target = self.root / ("codex" + suffix)
            target.write_text("synthetic")
            target.chmod(0o700)
            with self.assertRaises(ValueError):
                self.plan(codex_exe=target)

    def test_links_refused(self):
        linked = self.root / "linked"
        try:
            linked.symlink_to(self.clash, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(ValueError):
            self.plan(clash_dir=linked)

    def test_electron_requires_bundle(self):
        with self.assertRaises(ValueError):
            self.plan(kind="electron")
        resources = self.root / "resources"
        resources.mkdir()
        (resources / "app.asar").write_bytes(b"synthetic")
        R["validate_executable"](str(self.exe), "electron")
        if os.name == "nt":
            self.plan(kind="electron")

    def test_child_launch_is_list_shell_false_parent_unchanged(self):
        self.installed()
        launch = R["launch"]
        parent = dict(os.environ)
        # Patch function globals rather than invoke any synthetic executable.
        with mock.patch.dict(launch.__globals__, {"check_listener": mock.Mock()}), \
             mock.patch.object(subprocess, "run", return_value=mock.Mock(returncode=7)) as run:
            args = ["a&b", "$(not-a-command)", 'quoted"argument', "with spaces"]
            self.assertEqual(launch(self.state / "config.json", args), 7)
        self.assertEqual(run.call_args.args[0], [str(self.exe), *args])
        self.assertIs(run.call_args.kwargs["shell"], False)
        self.assertEqual(dict(os.environ), parent)

    @unittest.skipUnless(os.name == "nt", "Desktop launch requires Windows instance verification")
    def test_desktop_running_refusal_and_flags(self):
        resources = self.root / "resources"
        resources.mkdir()
        (resources / "app.asar").write_bytes(b"synthetic")
        self.installed(kind="electron")
        launch = R["launch"]
        with mock.patch.dict(launch.__globals__, {"check_listener": mock.Mock(), "desktop_running": mock.Mock(return_value=True)}), \
             mock.patch.object(subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "already running"):
                launch(self.state / "config.json")
            run.assert_not_called()
        with mock.patch.dict(launch.__globals__, {"check_listener": mock.Mock(), "desktop_running": mock.Mock(return_value=False)}), \
             mock.patch.object(subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            launch(self.state / "config.json")
            argv = run.call_args.args[0]
            self.assertIn("--proxy-server=http://127.0.0.1:17891", argv)
            self.assertIn("--proxy-bypass-list=localhost;127.0.0.1;[::1]", argv)
            with self.assertRaises(ValueError):
                launch(self.state / "config.json", ["--proxy-server=elsewhere"])

    def test_runtime_refuses_edited_config_or_no_listener(self):
        self.installed()
        with mock.patch.dict(R["launch"].__globals__, {"check_listener": mock.Mock(side_effect=ValueError("No TCP listener"))}), \
             mock.patch.object(subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "No TCP listener"):
                R["launch"](self.state / "config.json")
            run.assert_not_called()
        (self.state / "config.json").write_text("{}")
        with self.assertRaises(ValueError):
            R["load_owned_config"](self.state / "config.json")

    def test_non_windows_desktop_preflight_refused(self):
        other_os = mock.Mock(wraps=os)
        other_os.name = "posix"
        with mock.patch.object(proxy, "os", other_os):
            for kind in ("electron", "owl"):
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    self.plan(kind=kind)
        self.assertFalse(self.state.exists())

    @unittest.skipUnless(os.name == "nt", "Experimental desktop launch is Windows-only")
    def test_owl_is_explicit_experimental_not_electron(self):
        resources = self.root / "resources"
        resources.mkdir()
        (resources / "app.asar").write_bytes(b"synthetic")
        with self.assertRaises(ValueError):
            self.plan(kind="owl")
        (resources / "owl-electron-app.json").write_text(json.dumps({"runtimeName": "owl"}))
        with self.assertRaisesRegex(ValueError, "not verified standard Electron"):
            self.plan(kind="electron")
        plan = self.plan(kind="owl")
        self.assertEqual(plan["compatibility"], "unverified-owl-proxy-flag")
        self.assertTrue(any("EXPERIMENTAL" in warning for warning in plan["warnings"]))
        self.assertEqual(proxy.install(plan)["kind"], "owl")
        self.assertFalse(self.state.exists())

    def test_runtime_rejects_config_extras_and_remote_proxy(self):
        config = json.loads(self.plan()["files"]["config.json"])
        for update in ({"proxy_url": "http://example.invalid:123"}, {"proxy_url": "socks5://127.0.0.1:123"},
                       {"extra": "synthetic"}, {"version": True}, {"owner": "other"}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                R["validate_config"](dict(config, **update))

    def test_desktop_inventory_fail_closed_and_path_match(self):
        if os.name != "nt":
            with self.assertRaisesRegex(ValueError, "unsupported"):
                R["desktop_running"](self.exe)
            return
        shell = self.root / "system" / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        shell.parent.mkdir(parents=True)
        shell.write_bytes(b"synthetic; never run")
        root = str(self.root / "system")
        with mock.patch.dict(os.environ, {"SystemRoot": root}):
            for rows, expected in [([{"Name": self.exe.name, "ExecutablePath": str(self.exe)}], True),
                                   ([{"Name": self.exe.name, "ExecutablePath": str(self.root / "other" / self.exe.name)}], False)]:
                result = mock.Mock(stdout=json.dumps(rows), returncode=0)
                with mock.patch.object(subprocess, "run", return_value=result) as run:
                    self.assertEqual(R["desktop_running"](self.exe), expected)
                    self.assertIs(run.call_args.kwargs["shell"], False)
                    command = run.call_args.args[0][-1]
                    self.assertNotIn(str(self.exe), command)
                    self.assertNotIn("CommandLine", command)
                    self.assertIn("Name,ExecutablePath", command)
            for output in ("not json", "null", json.dumps([{"Name": self.exe.name, "ExecutablePath": None}])):
                with mock.patch.object(subprocess, "run", return_value=mock.Mock(stdout=output)):
                    with self.assertRaises(ValueError):
                        R["desktop_running"](self.exe)
            with mock.patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 1)):
                with self.assertRaises(ValueError):
                    R["desktop_running"](self.exe)

    @unittest.skipUnless(os.name == "nt", "Windows batch encoding bootstrap")
    def test_unicode_wrapper_has_ascii_utf8_bootstrap(self):
        state = self.root / "synthetic-状态"
        python = str(self.root / "synthetic-解释器" / "python.exe")
        wrapper = proxy._wrapper(python, state)
        bootstrap = wrapper[:wrapper.index('"' + python + '"')]
        bootstrap.encode("ascii")
        self.assertIn('"%SystemRoot%\\System32\\chcp.com" 65001 >nul\r\n', bootstrap)
        self.assertIn("if errorlevel 1 exit /b 1\r\n", bootstrap)
        self.assertIn(str(state / "launch_codex.py").encode("utf-8"), wrapper.encode("utf-8"))
        self.assertNotIn("%*", wrapper)

    def test_wrapper_metacharacters(self):
        if os.name == "nt":
            for bad in ("percent%", "amp&", "bang!", "paren("):
                with self.assertRaises(ValueError):
                    self.plan(state_dir=self.root / bad)
            wrapper = self.plan()["files"][proxy.WRAPPER]
            self.assertNotIn("%*", wrapper)
            self.assertIn('" -I "', wrapper)
        else:
            plan = self.plan(state_dir=self.root / "space ' & $(literal)")
            self.assertIn(' "$@"', plan["files"][proxy.WRAPPER])


if __name__ == "__main__":
    unittest.main()
