"""Install this skill into personal Claude Code and/or Codex skill directories."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import uuid

NAME = 'clash-codex-optimizer'
OWNER = 'blues19-clash-codex-skill'
MANIFEST = '.package-manifest.json'
SOURCE = Path(__file__).resolve().parent.parent
FILES = (
    'SKILL.md',
    'assets/countries.json',
    'assets/global-script.template.js',
    'assets/global-script.js',
    'scripts/build.cjs',
    'scripts/install.py',
    'scripts/install_skill.py',
    'scripts/configure.py',
    'scripts/codex_proxy.py',
    'assets/launch_codex.py',
)


class SkillInstallError(Exception):
    pass


def safe_path(path):
    path = Path(os.path.abspath(path))
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise SkillInstallError('Symlink/junction skill destinations are not supported.')
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise SkillInstallError('Invalid destination directory.')
    return path


def read_file(path):
    path = safe_path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise SkillInstallError('Package entries must be regular files.')
    return path.read_bytes()


def snapshot(source):
    # Only these explicit files are ever read/copied from the source package.
    return {rel: read_file(Path(source) / rel) for rel in FILES}


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SkillInstallError('Duplicate package manifest key.')
        result[key] = value
    return result


def safe_relative(rel):
    # Canonical POSIX paths only; reject Windows drive, UNC, ADS and traversal
    # syntax even when validation is performed on a different platform.
    return (isinstance(rel, str) and bool(rel) and '\\' not in rel
            and ':' not in rel and '\x00' not in rel
            and all(part not in ('', '.', '..') for part in rel.split('/'))
            and rel != MANIFEST)


def existing_snapshot(destination):
    """Validate a historical package against its own strict integrity record."""
    safe_path(destination)
    if not destination.is_dir():
        raise SkillInstallError('Skill destination is not a directory.')
    try:
        raw = read_file(destination / MANIFEST)
        manifest = json.loads(raw.decode('utf-8'), object_pairs_hook=strict_object)
    except (ValueError, UnicodeError, FileNotFoundError):
        raise SkillInstallError('Existing skill has no valid package manifest.') from None
    if (not isinstance(manifest, dict) or set(manifest) != {'owner', 'files'}
            or manifest['owner'] != OWNER or not isinstance(manifest['files'], dict)
            or not manifest['files']):
        raise SkillInstallError('Existing skill has no valid package ownership record.')
    hashes = manifest['files']
    for rel, digest in hashes.items():
        if (not safe_relative(rel) or not isinstance(digest, str)
                or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise SkillInstallError('Invalid package manifest path or hash.')
    actual = {}
    directories = set()

    def walk_error(error):
        raise error

    for root, dirs, names in os.walk(destination, followlinks=False, onerror=walk_error):
        for name in dirs:
            path = safe_path(Path(root) / name)
            directories.add(path.relative_to(destination).as_posix())
        for name in names:
            path = Path(root) / name
            rel = path.relative_to(destination).as_posix()
            actual[rel] = read_file(path)
    if set(actual) != set(hashes) | {MANIFEST}:
        raise SkillInstallError('Existing skill has extra/missing files; preserve it and integrate manually.')
    expected_dirs = {parent.as_posix() for rel in hashes
                     for parent in Path(rel).parents if parent != Path('.')}
    if directories != expected_dirs:
        raise SkillInstallError('Existing skill has custom directories; refusing overwrite.')
    if actual[MANIFEST] != raw or any(hashlib.sha256(actual[rel]).hexdigest() != digest
                                    for rel, digest in hashes.items()):
        raise SkillInstallError('Existing skill differs from its manifest; refusing overwrite.')
    return actual


def verify_destination(destination, previous):
    safe_path(destination)
    if previous is None:
        if destination.exists():
            raise SkillInstallError('Destination appeared during installation; no replacement made.')
    elif not destination.exists() or existing_snapshot(destination) != previous:
        raise SkillInstallError('Destination changed during installation; no replacement made.')


def install_skill(home, client, *, apply=False, source=SOURCE, upgrade=False):
    if client not in ('claude', 'codex'):
        raise SkillInstallError('Unknown skill client.')
    home = safe_path(home)
    if not home.is_dir():
        raise SkillInstallError('Home directory must already exist.')
    client_root = home / ('.claude' if client == 'claude' else '.agents')
    parent = client_root / 'skills'
    destination = safe_path(parent / NAME)
    files = snapshot(source)
    hashes = {rel: hashlib.sha256(data).hexdigest() for rel, data in files.items()}
    previous = existing_snapshot(destination) if destination.exists() else None
    if previous is not None:
        if {rel: data for rel, data in previous.items() if rel != MANIFEST} == files:
            return {'client': client, 'applied': False, 'status': 'already-current', 'target': str(destination)}
        if not upgrade:
            raise SkillInstallError('Existing managed skill differs; use --upgrade for a verified package upgrade.')
    if not apply:
        return {'client': client, 'applied': False,
                'status': 'upgrade-preview' if previous is not None else 'preview',
                'target': str(destination)}
    safe_path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    safe_path(parent)
    # Staging and old packages stay outside skills/, where clients discover skills.
    backup_root = safe_path(client_root / 'clash-codex-skill-backups')
    backup_root.mkdir(exist_ok=True)
    safe_path(backup_root)
    operation = uuid.uuid4().hex
    staging = backup_root / ('.stage-' + operation)
    backup = backup_root / (NAME + '-' + operation)
    staging.mkdir()
    moved = False
    published = False
    try:
        for rel, data in files.items():
            file = staging / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        (staging / MANIFEST).write_text(json.dumps({'owner': OWNER, 'files': hashes}, indent=2) + '\n', encoding='utf-8')
        verify_destination(destination, previous)
        safe_path(backup_root)
        if previous is not None:
            destination.rename(backup)
            moved = True
            # Also check the renamed directory before publishing. A concurrent
            # edit must not be silently replaced, even across the rename window.
            if existing_snapshot(backup) != previous:
                raise SkillInstallError('Destination changed during installation; no replacement made.')
        verify_destination(destination, None)
        staging.rename(destination)
        published = True
    except BaseException:
        if moved and not published:
            safe_path(destination)
            safe_path(backup)
            if destination.exists():
                raise SkillInstallError('Publish failed and destination appeared; previous package retained in backup.') from None
            backup.rename(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    result = {'client': client, 'applied': True,
              'status': 'upgraded' if moved else 'installed', 'target': str(destination)}
    if moved:
        result['backup'] = str(backup)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=('claude', 'codex', 'both'), default='both')
    parser.add_argument('--home', type=Path, default=Path.home(), help='Personal home; tests may supply a temporary home')
    parser.add_argument('--apply', action='store_true', help='Write skill directories; default is preview')
    parser.add_argument('--upgrade', action='store_true', help='Upgrade only unedited, manifest-verified managed skills')
    args = parser.parse_args(argv)
    try:
        clients = ('claude', 'codex') if args.target == 'both' else (args.target,)
        # Preflight every destination before writing either one.
        for client in clients:
            install_skill(args.home, client, apply=False, upgrade=args.upgrade)
        for client in clients:
            print(json.dumps(install_skill(args.home, client, apply=args.apply, upgrade=args.upgrade), ensure_ascii=True))
        return 0
    except SkillInstallError as error:
        print('Error: ' + str(error), file=sys.stderr)
    except OSError:
        print('Error: skill filesystem operation failed; existing skills were not intentionally overwritten.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
