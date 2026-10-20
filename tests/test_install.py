"""Installer tests use synthetic directories and never inspect live configuration."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "clash-codex-optimizer" / "scripts" / "install.py"
spec = importlib.util.spec_from_file_location("clash_installer", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "synthetic-clash"
        self.root.mkdir()
        self.bundle = self.base / "bundled-placeholder.js"
        self.content = installer.HEADER + b"\nfunction main(config, profileName) { return config; }\n"
        self.bundle.write_bytes(self.content)
        self.target = self.root / "profiles" / "Script.js"

    def install(self, apply=False, reviewed_sha256=None):
        return installer.install(self.root, apply=apply, bundle_path=self.bundle,
                                 reviewed_sha256=reviewed_sha256)

    def seed(self, data):
        self.target.parent.mkdir(exist_ok=True)
        self.target.write_bytes(data)

    def snapshot(self):
        return {str(p.relative_to(self.base)): p.read_bytes() if p.is_file() else None
                for p in self.base.rglob("*")}

    def manifest(self, result):
        path = Path(result["manifest"])
        return path, json.loads(path.read_text(encoding="utf-8"))

    def test_dry_run_creates_nothing(self):
        before = self.snapshot()
        result = self.install()
        self.assertFalse(result["applied"])
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.target.parent.exists())

    def test_fresh_apply_and_restore_absence(self):
        result = self.install(True)
        self.assertEqual(self.target.read_bytes(), self.content)
        path, document = self.manifest(result)
        self.assertFalse(document["previous_exists"])
        self.assertEqual(document["target"], str(self.target))
        self.assertEqual(document["previous_sha256"], installer.sha256(b""))
        self.assertEqual((path.parent / "previous.bin").read_bytes(), b"")
        before = self.snapshot()
        installer.restore(self.root, path)
        self.assertEqual(before, self.snapshot())
        installer.restore(self.root, path, apply=True)
        self.assertFalse(self.target.exists())
        self.assertTrue(path.exists())

    def test_default_stub_preserves_original_bytes(self):
        original = b"\xef\xbb\xbf// default\r\nfunction /* note */ main (config, profileName) {\r\n return config;\r\n}\r\n"
        self.seed(original)
        result = self.install(True)
        path, document = self.manifest(result)
        self.assertTrue(document["previous_exists"])
        self.assertEqual((path.parent / "previous.bin").read_bytes(), original)
        installer.restore(self.root, path, apply=True)
        self.assertEqual(self.target.read_bytes(), original)

    def test_empty_existing_file_restores_existing_empty_file(self):
        self.seed(b"")
        result = self.install(True)
        installer.restore(self.root, result["manifest"], apply=True)
        self.assertTrue(self.target.is_file())
        self.assertEqual(self.target.read_bytes(), b"")

    def test_safe_default_recognition(self):
        for data in (b"", b" \r\n", b"// note\n/* only comments */",
                     b"function main(config,profileName){return config;}"):
            with self.subTest(data=data):
                self.assertTrue(installer.is_default(data))
        for data in (b"fun/**/ction main(config,profileName){return config;}",
                     b"function main(config,profileName){return config;}evil()",
                     b"function main(config,profileName){return config.other;}",
                     b"/* unterminated", b"\xff"):
            with self.subTest(data=data):
                self.assertFalse(installer.is_default(data))

    def test_custom_and_spoofed_header_refused_without_writes(self):
        for data in (b"function main(c) { return modify(c); }",
                     installer.HEADER + b"\n// custom script\nmodified();"):
            self.seed(data)
            before = self.snapshot()
            for apply in (False, True):
                with self.assertRaises(installer.InstallError):
                    self.install(apply)
                self.assertEqual(before, self.snapshot())

    def test_reviewed_exact_custom_replacement_backed_up_and_restorable(self):
        original = b'// private pre-public local script\r\ncustom();\r\n'
        self.seed(original)
        digest = installer.sha256(original)
        before = self.snapshot()
        with self.assertRaises(installer.InstallError):
            self.install(True)
        preview = self.install(reviewed_sha256=digest)
        self.assertTrue(preview['reviewed_replacement'])
        self.assertEqual(before, self.snapshot())
        result = self.install(True, reviewed_sha256=digest)
        self.assertTrue(result['reviewed_replacement'])
        path, document = self.manifest(result)
        self.assertEqual(document['previous_sha256'], digest)
        self.assertEqual((path.parent / 'previous.bin').read_bytes(), original)
        self.assertEqual(self.target.read_bytes(), self.content)
        with self.assertRaises(installer.InstallError):
            self.install(True, reviewed_sha256=digest)
        installer.restore(self.root, path, apply=True)
        self.assertEqual(self.target.read_bytes(), original)

    def test_reviewed_hash_invalid_absent_or_mismatched_refuses_without_writes(self):
        for exists in (False, True):
            if exists:
                self.seed(b'custom();')
            for digest in ('', '0' * 63, 'g' * 64, 'A' * 64, '0' * 64,
                           '../Script.js', 123, installer.sha256(b'')):
                for apply in (False, True):
                    with self.subTest(exists=exists, digest=digest, apply=apply):
                        before = self.snapshot()
                        with self.assertRaises(installer.InstallError):
                            self.install(apply, reviewed_sha256=digest)
                        self.assertEqual(before, self.snapshot())

    def test_reviewed_concurrent_change_still_refused(self):
        self.seed(b'custom reviewed bytes')
        digest = installer.sha256(self.target.read_bytes())
        original_verify = installer.verify_unchanged
        calls = 0

        def change_before_replace(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.target.write_bytes(b'new unreviewed private bytes')
            return original_verify(*args)

        with mock.patch.object(installer, 'verify_unchanged', side_effect=change_before_replace):
            with self.assertRaises(installer.InstallError):
                self.install(True, reviewed_sha256=digest)
        self.assertEqual(self.target.read_bytes(), b'new unreviewed private bytes')

    def test_reviewed_cli_prints_marker_not_script(self):
        original = b'private pre-public local script'
        self.seed(original)
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(installer, 'BUNDLE', self.bundle):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                code = installer.main(['--clash-dir', str(self.root), '--apply',
                                       '--reviewed-sha256', installer.sha256(original)])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())['reviewed_replacement'])
        self.assertNotIn(original.decode(), output.getvalue() + errors.getvalue())

    def test_exact_current_bundle_recognized_without_manifest(self):
        self.seed(self.content)
        self.install(True)
        self.assertEqual(self.target.read_bytes(), self.content)

    def test_managed_upgrade_requires_valid_manifest(self):
        first = self.install(True)
        old_bundle = self.content
        self.bundle.write_bytes(installer.HEADER + b"\n// upgraded\nfunction main(c) { return c; }\n")
        second = self.install(True)
        self.assertNotEqual(first["manifest"], second["manifest"])
        installer.restore(self.root, second["manifest"], apply=True)
        self.assertEqual(self.target.read_bytes(), old_bundle)
        Path(first["manifest"]).unlink()
        # The second manifest records only the new installed hash, not the old one.
        with self.assertRaises(installer.InstallError):
            self.install(True)

    def test_invalid_manifest_does_not_authorize_upgrade(self):
        result = self.install(True)
        path, document = self.manifest(result)
        document["target"] = str(self.base / "wrong.js")
        path.write_text(json.dumps(document), encoding="utf-8")
        self.bundle.write_bytes(installer.HEADER + b"\nnewVersion();\n")
        with self.assertRaises(installer.InstallError):
            self.install(True)

    def test_edited_managed_file_refuses_upgrade_and_restore(self):
        result = self.install(True)
        edited = self.target.read_bytes() + b"\nuserEdit();"
        self.target.write_bytes(edited)
        before = self.snapshot()
        with self.assertRaises(installer.InstallError):
            self.install(True)
        for apply in (False, True):
            with self.assertRaises(installer.InstallError):
                installer.restore(self.root, result["manifest"], apply=apply)
        self.assertEqual(before, self.snapshot())

    def test_corrupt_backup_refused(self):
        result = self.install(True)
        path = Path(result["manifest"])
        (path.parent / "previous.bin").write_bytes(b"corrupt")
        before = self.snapshot()
        with self.assertRaises(installer.InstallError):
            installer.restore(self.root, path, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_manifest_location_wrong_target_and_traversal(self):
        result = self.install(True)
        path, original = self.manifest(result)
        arbitrary = self.base / "manifest.json"
        arbitrary.write_text(json.dumps(original), encoding="utf-8")
        with self.assertRaises(installer.InstallError):
            installer.restore(self.root, arbitrary, apply=True)
        cases = [dict(original, target=str(self.root / "profiles" / ".." / "Script.js")),
                 dict(original, target=str(self.base / "other.js")),
                 dict(original, backup="../../secret"),
                 dict(original, version=True), dict(original, version=999),
                 dict(original, previous_exists="false"),
                 dict(original, installed_sha256="not-a-hash"), []]
        for document in cases:
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.subTest(document=document):
                with self.assertRaises(installer.InstallError):
                    installer.restore(self.root, path, apply=True)
                self.assertEqual(self.target.read_bytes(), self.content)

    def test_unicode_path(self):
        self.root = self.base / "clash-配置-é"
        self.root.mkdir()
        self.target = self.root / "profiles" / "Script.js"
        result = self.install(True)
        installer.restore(self.root, result["manifest"], apply=True)
        self.assertFalse(self.target.exists())

    def test_duplicate_backups_are_unique(self):
        first = self.install(True)
        second = self.install(True)
        self.assertNotEqual(first["manifest"], second["manifest"])
        self.assertTrue(Path(first["manifest"]).exists())
        self.assertTrue(Path(second["manifest"]).exists())

    def test_concurrent_edit_before_replace_is_preserved(self):
        self.seed(b"")
        original_verify = installer.verify_unchanged
        calls = 0

        def change_before_recheck(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.target.write_bytes(b"concurrent user edit")
            return original_verify(*args)

        with mock.patch.object(installer, "verify_unchanged", side_effect=change_before_recheck):
            with self.assertRaises(installer.InstallError):
                self.install(True)
        self.assertEqual(self.target.read_bytes(), b"concurrent user edit")
        self.assertFalse(list(self.target.parent.glob("*.tmp")))

    def test_invalid_bundle_refused_without_writes(self):
        for content in (b"", b"function main(c) { return c; }"):
            self.bundle.write_bytes(content)
            before = self.snapshot()
            with self.assertRaises(installer.InstallError):
                self.install(True)
            self.assertEqual(before, self.snapshot())

    def make_link(self, link, destination, directory=False):
        try:
            link.symlink_to(destination, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable on this platform")

    def test_explicit_directory_symlink_refused(self):
        link = self.base / "linked-root"
        self.make_link(link, self.root, True)
        with self.assertRaises(installer.InstallError):
            installer.install(link, apply=True, bundle_path=self.bundle)

    def test_parent_and_destination_symlinks_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.make_link(self.root / "profiles", outside, True)
        with self.assertRaises(installer.InstallError):
            self.install(True)
        (self.root / "profiles").unlink()
        self.target.parent.mkdir()
        other_file = outside / "untouched.js"
        other_file.write_bytes(b"")
        self.make_link(self.target, other_file)
        with self.assertRaises(installer.InstallError):
            self.install(True)
        self.assertEqual(other_file.read_bytes(), b"")

    def test_backup_symlink_refused(self):
        result = self.install(True)
        backup = Path(result["manifest"]).parent / "previous.bin"
        backup.unlink()
        other = self.base / "outside-backup"
        other.write_bytes(b"")
        self.make_link(backup, other)
        with self.assertRaises(installer.InstallError):
            installer.restore(self.root, result["manifest"], apply=True)

    def test_reparse_point_refused_without_link_privileges(self):
        original_lstat = Path.lstat

        def simulated_reparse(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            if path == self.root:
                fake = mock.Mock()
                fake.st_mode = info.st_mode
                fake.st_file_attributes = 0x400
                return fake
            return info

        with mock.patch.object(Path, "lstat", simulated_reparse):
            with self.assertRaises(installer.InstallError):
                self.install(True)
        self.assertFalse(self.target.parent.exists())

    def test_spoofed_managed_default_requires_hash_verification(self):
        self.seed(installer.HEADER + b"\nfunction main(config,profileName){return config;}")
        with self.assertRaises(installer.InstallError):
            self.install(True)

    def test_restore_concurrent_edit_is_preserved(self):
        self.seed(b"// original default\n")
        result = self.install(True)
        original_verify = installer.verify_unchanged

        def change_before_recheck(*args):
            self.target.write_bytes(b"concurrent restore edit")
            return original_verify(*args)

        with mock.patch.object(installer, "verify_unchanged", side_effect=change_before_recheck):
            with self.assertRaises(installer.InstallError):
                installer.restore(self.root, result["manifest"], apply=True)
        self.assertEqual(self.target.read_bytes(), b"concurrent restore edit")

    def test_repository_target_refused(self):
        with mock.patch.object(installer, "REPOSITORY", self.base):
            with self.assertRaises(installer.InstallError):
                self.install(True)

    def test_cli_dry_run_and_concise_failure(self):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(installer, "BUNDLE", self.bundle):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(installer.main(["--clash-dir", str(self.root)]), 0)
                self.seed(b"private-config-must-not-be-logged")
                self.assertEqual(installer.main(["--clash-dir", str(self.root), "--apply"]), 1)
        self.assertNotIn("private-config-must-not-be-logged", output.getvalue() + errors.getvalue())
        self.assertIn("Error:", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
