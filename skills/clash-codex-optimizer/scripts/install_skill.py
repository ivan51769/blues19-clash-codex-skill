"""Install this skill into personal Claude Code and/or Codex skill directories."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import uuid

NAME = 'clash-codex-optimizer'
SOURCE = Path(__file__).resolve().parent.parent
FILES = (
    'SKILL.md',
    'assets/countries.json',
    'assets/global-script.template.js',
    'assets/global-script.js',
    'scripts/build.cjs',
    'scripts/install.py',
    'scripts/install_skill.py',
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


def snapshot(source):
    result = {}
    for rel in FILES:
        path = safe_path(source / rel)
        result[rel] = path.read_bytes()
    return result


def install_skill(home, client, *, apply=False, source=SOURCE):
    if client not in ('claude', 'codex'):
        raise SkillInstallError('Unknown skill client.')
    home = safe_path(home)
    if not home.is_dir():
        raise SkillInstallError('Home directory must already exist.')
    parent = home / ('.claude' if client == 'claude' else '.agents') / 'skills'
    destination = safe_path(parent / NAME)
    files = snapshot(source)
    hashes = {rel: hashlib.sha256(data).hexdigest() for rel, data in files.items()}
    if destination.exists():
        if not destination.is_dir():
            raise SkillInstallError('Skill destination is not a directory.')
        actual = set()
        for root, dirs, names in os.walk(destination, followlinks=False):
            for name in dirs:
                safe_path(Path(root) / name)
            for name in names:
                path = safe_path(Path(root) / name)
                actual.add(path.relative_to(destination).as_posix())
        expected = set(FILES) | {'.package-manifest.json'}
        if actual != expected:
            raise SkillInstallError('Existing skill has extra/missing files; preserve it and integrate manually.')
        try:
            manifest = json.loads((destination / '.package-manifest.json').read_text(encoding='utf-8'))
        except (ValueError, UnicodeError):
            raise SkillInstallError('Existing skill has no valid package manifest.') from None
        if manifest != {'owner': 'blues19-clash-codex-skill', 'files': hashes} or any((destination / rel).read_bytes() != data for rel, data in files.items()):
            raise SkillInstallError('Existing skill differs; refusing overwrite. Back it up and update manually.')
        return {'client': client, 'applied': False, 'status': 'already-current', 'target': str(destination)}
    if not apply:
        return {'client': client, 'applied': False, 'status': 'preview', 'target': str(destination)}
    safe_path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    safe_path(parent)
    staging = parent / ('.' + NAME + '.install-' + uuid.uuid4().hex)
    staging.mkdir()
    try:
        for rel, data in files.items():
            file = staging / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        (staging / '.package-manifest.json').write_text(json.dumps({'owner': 'blues19-clash-codex-skill', 'files': hashes}, indent=2) + '\n', encoding='utf-8')
        safe_path(destination)
        if destination.exists():
            raise SkillInstallError('Destination appeared during installation; no replacement made.')
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {'client': client, 'applied': True, 'status': 'installed', 'target': str(destination)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=('claude', 'codex', 'both'), default='both')
    parser.add_argument('--home', type=Path, default=Path.home(), help='Personal home; tests may supply a temporary home')
    parser.add_argument('--apply', action='store_true', help='Write new skill directories; default is preview')
    args = parser.parse_args(argv)
    try:
        clients = ('claude', 'codex') if args.target == 'both' else (args.target,)
        # Preflight every destination before writing either one.
        for client in clients:
            install_skill(args.home, client, apply=False)
        for client in clients:
            print(json.dumps(install_skill(args.home, client, apply=args.apply), ensure_ascii=True))
        return 0
    except SkillInstallError as error:
        print('Error: ' + str(error), file=sys.stderr)
    except OSError:
        print('Error: skill filesystem operation failed; existing skills were not intentionally overwritten.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
