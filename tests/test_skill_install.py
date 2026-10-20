import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'skills' / 'clash-codex-optimizer' / 'scripts' / 'install_skill.py'
spec = importlib.util.spec_from_file_location('skill_installer', SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SkillInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'synthetic-home'
        self.home.mkdir()
        self.source = self.root / 'source'
        for rel in installer.FILES:
            path = self.source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic ' + rel, encoding='utf-8')

    def run_install(self, client='codex', apply=False, upgrade=False):
        return installer.install_skill(self.home, client, apply=apply, source=self.source, upgrade=upgrade)

    def tree(self, root=None):
        root = self.home if root is None else root
        return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
                for p in root.rglob('*')}

    def old_package(self, client='codex'):
        # An earlier managed release can have both fewer and retired files.
        target = Path(self.run_install(client, apply=True)['target'])
        (target / 'scripts/configure.py').unlink()
        (target / 'scripts/retired.py').write_bytes(b'old retired script')
        (target / 'SKILL.md').write_bytes(b'old release skill')
        self.write_manifest(target)
        return target

    def write_manifest(self, target):
        hashes = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in target.rglob('*') if p.is_file() and p.name != installer.MANIFEST}
        document = {'owner': installer.OWNER, 'files': hashes}
        (target / installer.MANIFEST).write_text(json.dumps(document), encoding='utf-8')
        return document

    def test_preview_creates_nothing(self):
        self.assertEqual(self.run_install()['status'], 'preview')
        self.assertEqual(list(self.home.iterdir()), [])

    def test_both_clients_install_to_personal_directories(self):
        for client, hidden in [('claude', '.claude'), ('codex', '.agents')]:
            result = self.run_install(client, apply=True)
            target = self.home / hidden / 'skills' / installer.NAME
            self.assertTrue(result['applied'])
            self.assertEqual((target / 'SKILL.md').read_text(encoding='utf-8'), 'synthetic SKILL.md')
            self.assertEqual(self.run_install(client, apply=True)['status'], 'already-current')

    def test_existing_custom_skill_is_not_overwritten(self):
        target = self.home / '.agents' / 'skills' / installer.NAME
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('custom', encoding='utf-8')
        with self.assertRaises(installer.SkillInstallError):
            self.run_install(apply=True)
        self.assertEqual((target / 'SKILL.md').read_text(encoding='utf-8'), 'custom')

    def test_edited_managed_skill_is_preserved(self):
        result = self.run_install(apply=True)
        target = Path(result['target'])
        (target / 'SKILL.md').write_text('custom edit', encoding='utf-8')
        with self.assertRaises(installer.SkillInstallError):
            self.run_install(apply=True)
        self.assertEqual((target / 'SKILL.md').read_text(encoding='utf-8'), 'custom edit')

    def test_upgrade_requires_opt_in_and_dry_run_has_zero_writes(self):
        self.old_package()
        before = self.tree()
        for apply in (False, True):
            with self.assertRaises(installer.SkillInstallError):
                self.run_install(apply=apply)
            self.assertEqual(before, self.tree())
        self.assertEqual(self.run_install(upgrade=True)['status'], 'upgrade-preview')
        self.assertEqual(before, self.tree())

    def test_verified_upgrade_adds_removes_and_preserves_old_package_outside_discovery(self):
        for client, hidden in [('claude', '.claude'), ('codex', '.agents')]:
            with self.subTest(client=client):
                target = self.old_package(client)
                old = self.tree(target)
                result = self.run_install(client, apply=True, upgrade=True)
                self.assertEqual(result['status'], 'upgraded')
                backup = Path(result['backup'])
                self.assertEqual(backup.parent, self.home / hidden / 'clash-codex-skill-backups')
                self.assertNotIn(self.home / hidden / 'skills', backup.parents)
                self.assertEqual(self.tree(backup), old)
                self.assertTrue((target / 'scripts/configure.py').is_file())
                self.assertFalse((target / 'scripts/retired.py').exists())
                before = self.tree()
                self.assertEqual(self.run_install(client, apply=True, upgrade=True)['status'], 'already-current')
                self.assertEqual(before, self.tree())

    def test_modified_managed_upgrade_refuses_without_writes(self):
        target = self.old_package()
        (target / 'scripts/retired.py').write_bytes(b'private custom edit')
        before = self.tree()
        for apply in (False, True):
            with self.assertRaises(installer.SkillInstallError):
                self.run_install(apply=apply, upgrade=True)
            self.assertEqual(before, self.tree())

    def test_strict_manifest_and_file_allowlist_refuse_unsafe_upgrades(self):
        target = self.old_package()
        manifest_path = target / installer.MANIFEST
        valid = json.loads(manifest_path.read_text(encoding='utf-8'))
        invalid = [
            dict(valid, owner='other-owner'), dict(valid, extra=True),
            {'owner': installer.OWNER}, dict(valid, files=[]), dict(valid, files={}),
        ]
        for rel in ('../outside', '/absolute', 'C:/absolute', 'C:relative',
                    'scripts/../escape', './SKILL.md', 'scripts//bad',
                    'scripts\\bad', '//server/share', installer.MANIFEST, ''):
            invalid.append(dict(valid, files=dict(valid['files'], **{rel: '0' * 64})))
        for digest in ('0' * 63, 'A' * 64, 'g' * 64, 123, None):
            invalid.append(dict(valid, files=dict(valid['files'], **{'SKILL.md': digest})))
        missing = dict(valid['files'])
        del missing['SKILL.md']
        invalid.append(dict(valid, files=missing))
        for document in invalid:
            with self.subTest(document=document):
                manifest_path.write_text(json.dumps(document), encoding='utf-8')
                before = self.tree()
                with self.assertRaises(installer.SkillInstallError):
                    self.run_install(apply=True, upgrade=True)
                self.assertEqual(before, self.tree())
        manifest_path.write_text(json.dumps(valid), encoding='utf-8')
        (target / 'private-config.yaml').write_bytes(b'private')
        before = self.tree()
        with self.assertRaises(installer.SkillInstallError):
            self.run_install(apply=True, upgrade=True)
        self.assertEqual(before, self.tree())

    def test_duplicate_manifest_keys_refused(self):
        target = self.old_package()
        path = target / installer.MANIFEST
        raw = path.read_text(encoding='utf-8')
        path.write_text('{"owner": "wrong", ' + raw[1:], encoding='utf-8')
        before = self.tree()
        with self.assertRaises(installer.SkillInstallError):
            self.run_install(apply=True, upgrade=True)
        self.assertEqual(before, self.tree())

    def test_publish_failure_restores_previous_files(self):
        target = self.old_package()
        old = self.tree(target)
        rename = Path.rename

        def fail_publish(path, destination):
            if path.name.startswith('.stage-'):
                raise OSError('injected publish failure')
            return rename(path, destination)

        with mock.patch.object(Path, 'rename', fail_publish):
            with self.assertRaises(OSError):
                self.run_install(apply=True, upgrade=True)
        self.assertEqual(old, self.tree(target))
        self.assertEqual(list((self.home / '.agents' / 'clash-codex-skill-backups').iterdir()), [])

    def test_staging_write_failure_leaves_previous_files(self):
        target = self.old_package()
        old = self.tree(target)
        write = Path.write_bytes

        def fail_stage_write(path, data):
            if any(part.startswith('.stage-') for part in path.parts):
                raise OSError('injected staging failure')
            return write(path, data)

        with mock.patch.object(Path, 'write_bytes', fail_stage_write):
            with self.assertRaises(OSError):
                self.run_install(apply=True, upgrade=True)
        self.assertEqual(old, self.tree(target))
        self.assertEqual(list((self.home / '.agents' / 'clash-codex-skill-backups').iterdir()), [])

    def test_custom_empty_directory_refuses_upgrade(self):
        target = self.old_package()
        (target / 'private-empty-directory').mkdir()
        before = self.tree()
        with self.assertRaises(installer.SkillInstallError):
            self.run_install(apply=True, upgrade=True)
        self.assertEqual(before, self.tree())

    def test_reparse_entry_refuses_upgrade_without_writes(self):
        target = self.old_package()
        before = self.tree()
        lstat = Path.lstat

        def reparse(path, *args, **kwargs):
            info = lstat(path, *args, **kwargs)
            if path == target / 'scripts':
                fake = mock.Mock()
                fake.st_mode = info.st_mode
                fake.st_file_attributes = 0x400
                return fake
            return info

        with mock.patch.object(Path, 'lstat', reparse):
            with self.assertRaises(installer.SkillInstallError):
                self.run_install(apply=True, upgrade=True)
        self.assertEqual(before, self.tree())

    def test_backup_swap_failure_leaves_previous_files(self):
        target = self.old_package()
        old = self.tree(target)
        rename = Path.rename

        def fail_swap(path, destination):
            if path == target:
                raise OSError('injected old-directory swap failure')
            return rename(path, destination)

        with mock.patch.object(Path, 'rename', fail_swap):
            with self.assertRaises(OSError):
                self.run_install(apply=True, upgrade=True)
        self.assertEqual(old, self.tree(target))
        self.assertEqual(list((self.home / '.agents' / 'clash-codex-skill-backups').iterdir()), [])

    def test_concurrent_change_during_staging_is_preserved(self):
        target = self.old_package()
        verify = installer.verify_destination

        def concurrent_change(destination, previous):
            (target / 'SKILL.md').write_bytes(b'concurrent custom change')
            return verify(destination, previous)

        with mock.patch.object(installer, 'verify_destination', side_effect=concurrent_change):
            with self.assertRaises(installer.SkillInstallError):
                self.run_install(apply=True, upgrade=True)
        self.assertEqual((target / 'SKILL.md').read_bytes(), b'concurrent custom change')
        self.assertTrue((target / 'scripts/retired.py').exists())

    def test_concurrent_change_across_backup_rename_restores_changed_original(self):
        target = self.old_package()
        rename = Path.rename

        def change_during_rename(path, destination):
            result = rename(path, destination)
            if path == target:
                (Path(destination) / 'SKILL.md').write_bytes(b'concurrent rename change')
            return result

        with mock.patch.object(Path, 'rename', change_during_rename):
            with self.assertRaises(installer.SkillInstallError):
                self.run_install(apply=True, upgrade=True)
        self.assertEqual((target / 'SKILL.md').read_bytes(), b'concurrent rename change')
        self.assertTrue((target / 'scripts/retired.py').exists())

    def test_cli_preflights_both_clients_with_upgrade_before_any_writes(self):
        calls = []

        def fake_install(home, client, *, apply=False, upgrade=False):
            calls.append((client, apply, upgrade))
            if client == 'codex' and not apply:
                raise installer.SkillInstallError('custom codex skill')
            return {'client': client}

        with mock.patch.object(installer, 'install_skill', side_effect=fake_install):
            with contextlib.redirect_stderr(io.StringIO()):
                code = installer.main(['--home', str(self.home), '--apply', '--upgrade'])
        self.assertEqual(code, 1)
        self.assertEqual(calls, [('claude', False, True), ('codex', False, True)])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_cli_upgrade_passes_flag_to_preflight_and_publish(self):
        with mock.patch.object(installer, 'install_skill', return_value={}) as install:
            with contextlib.redirect_stdout(io.StringIO()):
                code = installer.main(['--home', str(self.home), '--apply', '--upgrade'])
        self.assertEqual(code, 0)
        self.assertEqual(install.call_args_list, [
            mock.call(self.home, 'claude', apply=False, upgrade=True),
            mock.call(self.home, 'codex', apply=False, upgrade=True),
            mock.call(self.home, 'claude', apply=True, upgrade=True),
            mock.call(self.home, 'codex', apply=True, upgrade=True),
        ])

    def test_source_extra_file_is_not_copied(self):
        (self.source / 'subscription.yaml').write_text('synthetic-private-placeholder', encoding='utf-8')
        result = self.run_install(apply=True)
        self.assertFalse((Path(result['target']) / 'subscription.yaml').exists())
        (self.source / 'SKILL.md').write_bytes(b'new package release')
        result = self.run_install(apply=True, upgrade=True)
        self.assertFalse((Path(result['target']) / 'subscription.yaml').exists())
        self.assertFalse((Path(result['backup']) / 'subscription.yaml').exists())

    def test_invalid_client_and_missing_home_refused(self):
        with self.assertRaises(installer.SkillInstallError):
            installer.install_skill(self.home, 'unknown', source=self.source)
        with self.assertRaises(installer.SkillInstallError):
            installer.install_skill(self.root / 'missing', 'codex', source=self.source)

    def test_unicode_home(self):
        self.home = self.root / '用户 空格'
        self.home.mkdir()
        self.assertTrue(self.run_install(apply=True)['applied'])

    def test_manifest_is_an_integrity_record(self):
        result = self.run_install(apply=True)
        manifest = json.loads((Path(result['target']) / '.package-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['owner'], 'blues19-clash-codex-skill')
        self.assertEqual(set(manifest['files']), set(installer.FILES))


if __name__ == '__main__':
    unittest.main()
