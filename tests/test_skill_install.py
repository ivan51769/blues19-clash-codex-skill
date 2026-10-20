import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

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

    def run_install(self, client='codex', apply=False):
        return installer.install_skill(self.home, client, apply=apply, source=self.source)

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

    def test_source_extra_file_is_not_copied(self):
        (self.source / 'subscription.yaml').write_text('synthetic-private-placeholder', encoding='utf-8')
        result = self.run_install(apply=True)
        self.assertFalse((Path(result['target']) / 'subscription.yaml').exists())

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
