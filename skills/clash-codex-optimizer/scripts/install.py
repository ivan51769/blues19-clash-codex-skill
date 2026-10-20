"""Conservative installer for the bundled Clash global script (stdlib only)."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import uuid

HEADER = b"// Managed by blues19-clash-codex-skill"
VERSION = 1
BACKUPS = ".clash-codex-backups"
BUNDLE = Path(__file__).resolve().parent.parent / "assets" / "global-script.js"
REPOSITORY = Path(__file__).resolve().parents[3]


class InstallError(Exception):
    """A safe, user-facing refusal; never includes configuration content."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def absolute(path):
    # abspath normalizes '..' without following links.
    return Path(os.path.abspath(os.fspath(path)))


def check_path(path, *, directory=False):
    """Reject links and Windows junction/reparse points anywhere in a path."""
    path = absolute(path)
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise InstallError("Symlink or reparse-point paths are not supported.")
        if part != path or directory:
            if not stat.S_ISDIR(info.st_mode):
                raise InstallError("A required directory is not a directory.")
        elif not stat.S_ISREG(info.st_mode):
            raise InstallError("A required file is not a regular file.")
    return path


def locations(clash_dir):
    root = check_path(clash_dir, directory=True)
    if not root.is_dir():
        raise InstallError("The explicit Clash directory must already exist.")
    profiles = check_path(root / "profiles", directory=True)
    target = check_path(profiles / "Script.js")
    backups = check_path(profiles / BACKUPS, directory=True)
    if backups == REPOSITORY or REPOSITORY in backups.parents:
        raise InstallError("Backups must be outside the installer repository.")
    return target, backups


def read_state(target):
    check_path(target)
    try:
        return True, target.read_bytes()
    except FileNotFoundError:
        return False, b""


def has_header(data):
    return data.splitlines()[:1] == [HEADER]


def is_default(data):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    # Tokenize rather than deleting comments, which could join custom tokens.
    tokens = []
    position = 0
    pattern = re.compile(r"\s+|//[^\r\n]*|/\*[\s\S]*?\*/|[A-Za-z_$][A-Za-z0-9_$]*|[(){},;]")
    while position < len(text):
        match = pattern.match(text, position)
        if not match:
            return False
        token = match.group()
        if not token.isspace() and not token.startswith(("//", "/*")):
            tokens.append(token)
        position = match.end()
    return not tokens or tokens == [
        "function", "main", "(", "config", ",", "profileName", ")", "{",
        "return", "config", ";", "}",
    ]


def load_bundle(bundle_path=None):
    data = (Path(bundle_path) if bundle_path is not None else BUNDLE).read_bytes()
    if not data.strip() or not has_header(data):
        raise InstallError("Bundled script is empty or lacks its managed header.")
    return data


def load_manifest(manifest_path, target, backups):
    """Read only a manifest and its fixed sibling backup in the expected root."""
    manifest_path = absolute(manifest_path)
    if (manifest_path.name != "manifest.json"
            or manifest_path.parent.parent != backups):
        raise InstallError("Manifest is not in the expected backup directory.")
    check_path(manifest_path)
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise InstallError("Invalid backup manifest.") from None
    required = {"version", "target", "previous_exists", "previous_sha256",
                "installed_sha256", "backup_sha256"}
    if not isinstance(document, dict) or set(document) != required:
        raise InstallError("Invalid backup manifest shape.")
    if type(document["version"]) is not int or document["version"] != VERSION:
        raise InstallError("Unsupported backup manifest version.")
    if type(document["previous_exists"]) is not bool:
        raise InstallError("Invalid backup existence marker.")
    if not isinstance(document["target"], str) or document["target"] != str(target):
        raise InstallError("Backup manifest does not match the explicit target.")
    for key in ("previous_sha256", "installed_sha256", "backup_sha256"):
        if not isinstance(document[key], str) or not re.fullmatch(r"[0-9a-f]{64}", document[key]):
            raise InstallError("Invalid backup hash in manifest.")
    backup_path = check_path(manifest_path.parent / "previous.bin")
    data = backup_path.read_bytes()
    if sha256(data) != document["backup_sha256"] or sha256(data) != document["previous_sha256"]:
        raise InstallError("Backup integrity verification failed.")
    if not document["previous_exists"] and data != b"":
        raise InstallError("Invalid backup for an originally absent target.")
    return document, data


def managed_by_manifest(data, target, backups):
    if not backups.exists():
        return False
    check_path(backups, directory=True)
    for entry in backups.iterdir():
        # Do not follow arbitrary entries, even when a filename looks plausible.
        try:
            check_path(entry, directory=True)
            if not entry.is_dir():
                continue
            manifest, _ = load_manifest(entry / "manifest.json", target, backups)
            if manifest["installed_sha256"] == sha256(data):
                return True
        except (InstallError, OSError):
            continue
    return False


def verify_unchanged(clash_dir, target, expected):
    current_target, _ = locations(clash_dir)
    if current_target != target or read_state(target) != expected:
        raise InstallError("Destination changed during operation; no replacement made.")


def atomic_write(clash_dir, target, data, expected):
    """Stage locally, then revalidate both parents and original bytes."""
    check_path(target.parent, directory=True)
    fd, temporary = tempfile.mkstemp(prefix=".clash-codex-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        verify_unchanged(clash_dir, target, expected)
        os.replace(temporary, target)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def install(clash_dir, *, apply=False, bundle_path=None, reviewed_sha256=None):
    target, backups = locations(clash_dir)
    bundle = load_bundle(bundle_path)
    previous = read_state(target)
    exists, old = previous
    reviewed = reviewed_sha256 is not None
    if reviewed:
        if not isinstance(reviewed_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", reviewed_sha256):
            raise InstallError("Reviewed SHA-256 must be exactly 64 lowercase hexadecimal characters.")
        if not exists or sha256(old) != reviewed_sha256:
            raise InstallError("Reviewed SHA-256 does not match an existing global script.")
    if exists:
        if has_header(old):
            safe = sha256(old) == sha256(bundle) or managed_by_manifest(old, target, backups)
        else:
            safe = is_default(old)
        if not safe and not reviewed:
            raise InstallError("Refusing to overwrite a custom or edited global script.")
    if not apply:
        return {"action": "install", "applied": False, "target": str(target),
                "reviewed_replacement": reviewed}
    verify_unchanged(clash_dir, target, previous)
    target.parent.mkdir(exist_ok=True)
    check_path(target.parent, directory=True)
    backups.mkdir(exist_ok=True)
    check_path(backups, directory=True)
    # mkdir is exclusive: never reuse a previous operation's backup folder.
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex
    folder = backups / name
    folder.mkdir()
    check_path(folder, directory=True)
    manifest = {
        "version": VERSION, "target": str(target), "previous_exists": exists,
        "previous_sha256": sha256(old), "installed_sha256": sha256(bundle),
        "backup_sha256": sha256(old),
    }
    with (folder / "previous.bin").open("xb") as stream:
        stream.write(old)
        stream.flush()
        os.fsync(stream.fileno())
    manifest_path = folder / "manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    atomic_write(clash_dir, target, bundle, previous)
    return {"action": "install", "applied": True, "target": str(target),
            "manifest": str(manifest_path), "reviewed_replacement": reviewed}


def restore(clash_dir, manifest_path, *, apply=False):
    target, backups = locations(clash_dir)
    manifest, old = load_manifest(manifest_path, target, backups)
    current = read_state(target)
    if not current[0] or sha256(current[1]) != manifest["installed_sha256"]:
        raise InstallError("Current script differs from the installed version; refusing restore.")
    if apply:
        if manifest["previous_exists"]:
            atomic_write(clash_dir, target, old, current)
        else:
            verify_unchanged(clash_dir, target, current)
            target.unlink()
    return {"action": "restore", "applied": apply, "target": str(target)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clash-dir", required=True, help="Explicit existing Clash data directory")
    parser.add_argument("--apply", action="store_true", help="Write changes (default is read-only preview)")
    parser.add_argument("--restore", metavar="MANIFEST", help="Restore a verified installer backup")
    parser.add_argument("--reviewed-sha256", metavar="SHA256",
                        help="Allow replacement of exactly these reviewed existing script bytes (with backup)")
    args = parser.parse_args(argv)
    try:
        if args.restore and args.reviewed_sha256 is not None:
            raise InstallError("Reviewed SHA-256 is only supported for installation, not restore.")
        if args.restore:
            result = restore(args.clash_dir, args.restore, apply=args.apply)
        else:
            result = install(args.clash_dir, apply=args.apply, reviewed_sha256=args.reviewed_sha256)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except InstallError as error:
        print("Error: " + str(error), file=sys.stderr)
    except (OSError, ValueError, UnicodeError):
        # OS errors may contain private paths; do not print them or file contents.
        print("Error: filesystem operation failed; no configuration content was logged.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
