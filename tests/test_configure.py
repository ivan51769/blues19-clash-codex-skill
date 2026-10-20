import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'skills' / 'clash-codex-optimizer' / 'scripts' / 'configure.py'
spec = importlib.util.spec_from_file_location('combined_configurator_test', SCRIPT)
configure = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = configure
spec.loader.exec_module(configure)


class CombinedConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clash = self.root / 'synthetic-clash'
        (self.clash / 'profiles').mkdir(parents=True)
        self.script = self.clash / 'profiles' / 'Script.js'
        self.original = b'// default\r\nfunction main(config, profileName) { return config; }\r\n'
        self.script.write_bytes(self.original)
        self.exe = self.root / 'synthetic-codex.exe'
        self.exe.write_bytes(b'synthetic executable placeholder; never run')
        self.exe.chmod(0o700)
        self.state = self.root / 'launcher'
        self.server = socket.socket()
        self.server.bind(('127.0.0.1', 0))
        self.server.listen(16)
        self.server.settimeout(0.1)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.accept_connections, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        port = self.server.getsockname()[1]
        (self.clash / 'config.yaml').write_text('mixed-port: ' + str(port) + '\nsecret: synthetic-not-logged\n', encoding='utf-8')

    def accept_connections(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.server.accept()
                connection.close()
            except socket.timeout:
                continue
            except OSError:
                return

    def close_server(self):
        self.stop.set()
        self.server.close()
        self.thread.join(timeout=1)

    def run_configuration(self, apply=False, **kwargs):
        return configure.configure(self.clash, self.exe, 'cli', state_dir=self.state, apply=apply, **kwargs)

    def tree(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() if p.is_file() else None for p in self.root.rglob('*')}

    def test_combined_preview_is_zero_write_and_no_launch(self):
        before = self.tree()
        result = self.run_configuration()
        self.assertFalse(result['applied'])
        self.assertEqual(self.tree(), before)
        self.assertFalse(self.state.exists())

    def test_apply_writes_both_and_one_receipt_then_restores_both(self):
        result = self.run_configuration(apply=True)
        self.assertTrue(result['applied'])
        self.assertTrue(self.script.read_bytes().startswith(configure.clash.HEADER))
        self.assertTrue((self.state / 'config.json').exists())
        self.assertTrue(Path(result['codex']['launcher']).exists())
        receipt = Path(result['transaction'])
        record = json.loads(receipt.read_text(encoding='utf-8'))
        self.assertEqual(record['owner'], configure.OWNER)
        before = self.tree()
        preview = configure.restore(self.clash, receipt, state_dir=self.state)
        self.assertFalse(preview['applied'])
        self.assertEqual(self.tree(), before)
        restored = configure.restore(self.clash, receipt, state_dir=self.state, apply=True)
        self.assertTrue(restored['applied'])
        self.assertEqual(self.script.read_bytes(), self.original)
        self.assertFalse((self.state / 'config.json').exists())

    def test_proxy_preflight_failure_leaves_clash_unchanged(self):
        before = self.tree()
        with mock.patch.object(configure.proxy, 'prepare', side_effect=configure.proxy.ProxyError('synthetic refusal')):
            with self.assertRaises(configure.proxy.ProxyError):
                self.run_configuration(apply=True)
        self.assertEqual(self.tree(), before)

    def test_custom_global_script_blocks_both_without_review(self):
        self.script.write_bytes(b'custom script must stay')
        before = self.tree()
        with self.assertRaises(configure.clash.InstallError):
            self.run_configuration(apply=True)
        self.assertEqual(self.tree(), before)

    def test_exact_reviewed_custom_script_migrates_and_restores(self):
        custom = b'// explicitly reviewed synthetic legacy script\r\n'
        self.script.write_bytes(custom)
        result = self.run_configuration(apply=True, reviewed_sha256=configure.clash.sha256(custom))
        configure.restore(self.clash, result['transaction'], state_dir=self.state, apply=True)
        self.assertEqual(self.script.read_bytes(), custom)

    def test_second_component_failure_restores_global_bytes(self):
        original_install = configure.proxy.install
        def fail_apply(plan, apply=False):
            if apply:
                raise configure.proxy.ProxyError('synthetic second-step failure')
            return original_install(plan, apply=False)
        with mock.patch.object(configure.proxy, 'install', side_effect=fail_apply):
            with self.assertRaises(configure.ConfigurationError) as error:
                self.run_configuration(apply=True)
        self.assertEqual(error.exception.recovery['clash_rollback'], 'restored')
        self.assertEqual(self.script.read_bytes(), self.original)
        self.assertFalse((self.state / 'config.json').exists())

    def test_compensation_does_not_overwrite_a_concurrent_global_edit(self):
        original_install = configure.proxy.install
        edit = b'user edit during combined apply'
        def fail_after_edit(plan, apply=False):
            if apply:
                self.script.write_bytes(edit)
                raise configure.proxy.ProxyError('synthetic concurrent edit')
            return original_install(plan, apply=False)
        with mock.patch.object(configure.proxy, 'install', side_effect=fail_after_edit):
            with self.assertRaises(configure.ConfigurationError) as error:
                self.run_configuration(apply=True)
        self.assertIn('refused-or-failed', error.exception.recovery['clash_rollback'])
        self.assertEqual(self.script.read_bytes(), edit)

    def test_receipt_failure_rolls_back_both(self):
        with mock.patch.object(configure, 'write_receipt', side_effect=OSError('synthetic disk error')):
            with self.assertRaises(configure.ConfigurationError) as error:
                self.run_configuration(apply=True)
        self.assertEqual(error.exception.recovery['clash_rollback'], 'restored')
        self.assertEqual(error.exception.recovery['codex_rollback'], 'restored')
        self.assertEqual(self.script.read_bytes(), self.original)
        self.assertFalse((self.state / 'config.json').exists())

    def test_edited_proxy_blocks_combined_restore_before_global_write(self):
        result = self.run_configuration(apply=True)
        config_file = self.state / 'config.json'
        config_file.write_bytes(config_file.read_bytes() + b'\nuser edit')
        installed_script = self.script.read_bytes()
        with self.assertRaises(configure.proxy.ProxyError):
            configure.restore(self.clash, result['transaction'], state_dir=self.state, apply=True)
        self.assertEqual(self.script.read_bytes(), installed_script)
        self.assertTrue(config_file.read_bytes().endswith(b'user edit'))

    def test_second_restore_failure_reinstates_exact_global_bytes(self):
        result = self.run_configuration(apply=True)
        installed_script = self.script.read_bytes()
        original_restore = configure.proxy.restore
        def fail_apply(state, manifest, apply=False):
            if apply:
                raise configure.proxy.ProxyError('synthetic restore failure')
            return original_restore(state, manifest, apply=False)
        with mock.patch.object(configure.proxy, 'restore', side_effect=fail_apply):
            with self.assertRaises(configure.ConfigurationError) as error:
                configure.restore(self.clash, result['transaction'], state_dir=self.state, apply=True)
        self.assertEqual(error.exception.recovery['clash_compensation'], 'reinstated exact pre-restore bytes')
        self.assertEqual(self.script.read_bytes(), installed_script)

    def test_receipts_bind_exact_generations_and_restore_in_reverse_order(self):
        first = self.run_configuration(apply=True)
        second = self.run_configuration(apply=True)
        installed = self.script.read_bytes()
        with self.assertRaises(configure.proxy.ProxyError):
            configure.restore(self.clash, first['transaction'], state_dir=self.state, apply=True)
        self.assertEqual(self.script.read_bytes(), installed)
        configure.restore(self.clash, second['transaction'], state_dir=self.state, apply=True)
        configure.restore(self.clash, first['transaction'], state_dir=self.state, apply=True)
        self.assertEqual(self.script.read_bytes(), self.original)
        self.assertFalse(self.state.exists())

    def test_duplicate_receipt_keys_are_refused(self):
        result = self.run_configuration(apply=True)
        receipt = Path(result['transaction'])
        contents = receipt.read_text(encoding='utf-8')
        receipt.write_text('{"version":1,' + contents[1:], encoding='utf-8')
        with self.assertRaises(configure.ConfigurationError):
            configure.restore(self.clash, receipt, state_dir=self.state)

    def test_wrong_state_or_receipt_location_is_refused(self):
        result = self.run_configuration(apply=True)
        with self.assertRaises(configure.ConfigurationError):
            configure.restore(self.clash, result['transaction'], state_dir=self.root / 'wrong')
        copied = self.root / 'transaction.json'
        copied.write_bytes(Path(result['transaction']).read_bytes())
        with self.assertRaises(configure.ConfigurationError):
            configure.restore(self.clash, copied, state_dir=self.state)


if __name__ == '__main__':
    unittest.main()
