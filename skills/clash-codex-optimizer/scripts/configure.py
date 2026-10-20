"""Preview/apply Clash routing and a Codex-specific proxy launcher together."""

import argparse
import importlib.util
import json
import math
import re
import os
from pathlib import Path
import sys
import uuid

SCRIPTS = Path(__file__).resolve().parent
OWNER = 'blues19-clash-codex-skill'
VERSION = 1
TRANSACTIONS = '.clash-codex-transactions'
REPOSITORY = SCRIPTS.parents[2]


def load_local(name, filename):
    # Python -I must not resolve imports from an untrusted working directory.
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Keep the installed skill package immutable for hash-verified future upgrades.
sys.dont_write_bytecode = True
clash = load_local('clash_codex_global_installer', 'install.py')
proxy = load_local('clash_codex_proxy_installer', 'codex_proxy.py')
startup = load_local('clash_codex_startup_check', 'startup_check.py')


class ConfigurationError(Exception):
    def __init__(self, message, recovery=None):
        super().__init__(message)
        self.recovery = recovery or {}


def transaction_root(state_dir):
    state = clash.check_path(state_dir, directory=True)
    root = clash.check_path(state.parent / TRANSACTIONS, directory=True)
    if root == REPOSITORY or REPOSITORY in root.parents:
        raise ConfigurationError('Transaction state must be outside the public repository.')
    return state, root


def write_receipt(folder, document):
    clash.check_path(folder, directory=True)
    file = folder / 'transaction.json'
    descriptor = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, ensure_ascii=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return file


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError('Duplicate transaction key.')
        result[key] = value
    return result


def load_receipt(clash_dir, state_dir, receipt_path):
    state, root = transaction_root(state_dir)
    receipt = clash.check_path(receipt_path)
    if receipt.name != 'transaction.json' or receipt.parent.parent != root:
        raise ConfigurationError('Transaction is not in the expected local transaction directory.')
    if receipt.stat().st_size > 65536:
        raise ConfigurationError('Transaction record is unexpectedly large.')
    try:
        data = json.loads(receipt.read_text(encoding='utf-8'), object_pairs_hook=strict_object)
    except (ValueError, UnicodeError):
        raise ConfigurationError('Invalid transaction record.') from None
    keys = {'owner', 'version', 'clash_dir', 'state_dir', 'clash_manifest', 'codex_manifest'}
    if not isinstance(data, dict) or set(data) != keys or data.get('owner') != OWNER or type(data.get('version')) is not int or data['version'] != VERSION:
        raise ConfigurationError('Unsupported transaction record.')
    expected_clash = str(clash.check_path(clash_dir, directory=True))
    if data['clash_dir'] != expected_clash or data['state_dir'] != str(state):
        raise ConfigurationError('Transaction does not match the explicit target directories.')
    if not isinstance(data['clash_manifest'], str) or not isinstance(data['codex_manifest'], dict):
        raise ConfigurationError('Invalid component manifest generation.')
    return data


def repair_options(kind, desktop_action, action_id, log_dir, readiness_timeout):
    if desktop_action not in ('none', 'restart'):
        raise ConfigurationError('Unsupported desktop action.')
    if desktop_action == 'none':
        if action_id is not None or log_dir is not None:
            raise ConfigurationError('Action ID/log directory require an explicit desktop action.')
        return
    if kind not in ('electron', 'owl'):
        raise ConfigurationError('Desktop repair is not a CLI action.')
    if not isinstance(action_id, str) or not re.fullmatch(r'[0-9a-fA-F]{32}', action_id):
        raise ConfigurationError('Explicit desktop repair requires a single-use 32-hex action ID.')
    if (isinstance(readiness_timeout, bool) or not isinstance(readiness_timeout, (int, float))
            or not math.isfinite(readiness_timeout) or not 0 <= readiness_timeout <= 120):
        raise ConfigurationError('Readiness timeout must be 0 through 120 seconds.')
    # Metadata-only validation; no historical log contents are read by preview.
    startup.capture(log_dir)


def perform_desktop_repair(state, action_id, log_dir, readiness_timeout):
    report = startup.empty_report()
    try:
        baseline = startup.capture(log_dir)
    except (ValueError, OSError):
        return {'desktop': {'status': 'diagnostic_preflight_failed', 'close_attempted': False, 'start_attempted': False},
                'startup': report}
    try:
        action = proxy._runtime['repair_desktop'](state / 'config.json', action_id)
    except Exception:
        # Saved configuration remains valid. Never retry a lifecycle action here.
        return {'desktop': {'status': 'action_failed_unverified'}, 'startup': report}
    if action.get('status') == 'started':
        try:
            report = startup.watch(baseline, expected_pid=action['pid'], not_before=action['started_at'], timeout=readiness_timeout)
        except (ValueError, OSError, KeyError, TypeError):
            report['computer_use']['reason'] = 'fresh_log_observation_unavailable'
    else:
        report['computer_use']['reason'] = 'new_desktop_process_not_verified'
    return {'desktop': action, 'startup': report}


def configure(clash_dir, codex_exe, kind, *, state_dir=None, proxy_port=None, apply=False, reviewed_sha256=None,
              desktop_action='none', action_id=None, log_dir=None, readiness_timeout=60):
    repair_options(kind, desktop_action, action_id, log_dir, readiness_timeout)
    state, root = transaction_root(state_dir if state_dir is not None else proxy.default_state_dir())
    # Both read-only preflights must succeed before any configuration is written.
    clash_preview = clash.install(clash_dir, apply=False, reviewed_sha256=reviewed_sha256)
    plan = proxy.prepare(clash_dir, codex_exe, kind, state, proxy_port=proxy_port)
    proxy_preview = proxy.install(plan, apply=False)
    result = {'action': 'configure', 'applied': False, 'clash': clash_preview, 'codex': proxy_preview,
              'activation': 'Reapply the Clash global extension, then normally exit Codex and use the dedicated launcher. No process was started or stopped.'}
    if desktop_action == 'restart':
        result['desktop_action'] = {'requested': 'restart', 'action_id': action_id, 'requires_apply': True,
                                    'computer_use_verification': 'independent; unknown without explicit evidence'}
    if not apply:
        return result

    # Reserve receipt storage before touching either component.
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    clash.check_path(root, directory=True)
    folder = root / uuid.uuid4().hex
    folder.mkdir(mode=0o700)
    clash_result = clash.install(clash_dir, apply=True, reviewed_sha256=reviewed_sha256)
    proxy_result = None
    try:
        proxy_result = proxy.install(plan, apply=True)
        # Store the exact generation, not the mutable path to the newest manifest.
        generation = proxy_result['manifest_data']
        proxy.restore(state, generation, apply=False)
        document = {'owner': OWNER, 'version': VERSION,
                    'clash_dir': str(clash.check_path(clash_dir, directory=True)), 'state_dir': str(state),
                    'clash_manifest': clash_result['manifest'], 'codex_manifest': generation}
        receipt = write_receipt(folder, document)
    except Exception as error:
        # The proxy installer compensates its own partial writes before raising.
        recovery = {'clash_manifest': clash_result['manifest']}
        if proxy_result is not None:
            recovery['codex_manifest'] = proxy_result.get('manifest')
            try:
                if 'manifest_data' not in proxy_result:
                    raise ConfigurationError('Missing proxy generation; refusing ambiguous compensation.')
                proxy.restore(state, proxy_result['manifest_data'], apply=True)
                recovery['codex_rollback'] = 'restored'
            except Exception:
                recovery['codex_rollback'] = 'refused-or-failed; inspect local backup before manual recovery'
        else:
            try:
                proxy.install(plan, apply=False)
                recovery['codex_rollback'] = 'pre-apply state verified'
            except Exception:
                recovery['codex_rollback'] = 'not verified; preserve local state and inspect backups'
                recovery['codex_state_dir'] = str(state)
        try:
            clash.restore(clash_dir, clash_result['manifest'], apply=True)
            recovery['clash_rollback'] = 'restored'
        except Exception:
            recovery['clash_rollback'] = 'refused-or-failed; preserve edits and use the returned backup'
        raise ConfigurationError('Combined configuration did not complete; see component recovery status.', recovery) from error
    result.update({'applied': True, 'clash': clash_result, 'codex': proxy_result, 'transaction': str(receipt)})
    if desktop_action == 'restart':
        # Process lifecycle is not reversible configuration. Keep its outcome
        # outside the configuration transaction/compensation block.
        result.update(perform_desktop_repair(state, action_id, log_dir, readiness_timeout))
        result['activation'] = 'Configuration saved. Desktop action and capability evidence are separate; no security permission was changed. Do not automatically retry a restart.'
    return result


def restore(clash_dir, receipt_path, *, state_dir=None, apply=False):
    state = state_dir if state_dir is not None else proxy.default_state_dir()
    document = load_receipt(clash_dir, state, receipt_path)
    # Integrity and current-state checks for both components precede either write.
    clash_preview = clash.restore(clash_dir, document['clash_manifest'], apply=False)
    proxy_preview = proxy.restore(state, document['codex_manifest'], apply=False)
    result = {'action': 'restore', 'applied': False, 'clash': clash_preview, 'codex': proxy_preview}
    if not apply:
        return result
    target, backups = clash.locations(clash_dir)
    original_manifest, original_bytes = clash.load_manifest(document['clash_manifest'], target, backups)
    installed_before = clash.read_state(target)
    if not installed_before[0] or clash.sha256(installed_before[1]) != original_manifest['installed_sha256']:
        raise ConfigurationError('Clash script changed after restore preflight.')
    clash_result = clash.restore(clash_dir, document['clash_manifest'], apply=True)
    try:
        proxy_result = proxy.restore(state, document['codex_manifest'], apply=True)
    except Exception as error:
        recovery = {'codex_manifest': document['codex_manifest'], 'clash_manifest': document['clash_manifest']}
        try:
            expected = (original_manifest['previous_exists'], original_bytes)
            clash.atomic_write(clash_dir, target, installed_before[1], expected)
            recovery['clash_compensation'] = 'reinstated exact pre-restore bytes'
        except Exception:
            recovery['clash_compensation'] = 'refused-or-failed; preserve edits and inspect component backups'
        raise ConfigurationError('Combined restore did not complete; see recovery status.', recovery) from error
    result.update({'applied': True, 'clash': clash_result, 'codex': proxy_result})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clash-dir', required=True)
    parser.add_argument('--codex-exe', help='Actual installed executable, not a shim or app-server guessed as a desktop')
    parser.add_argument('--kind', choices=('cli', 'electron', 'owl'))
    parser.add_argument('--proxy-port', type=int, help='Explicit confirmed loopback HTTP/mixed port')
    parser.add_argument('--state-dir', type=Path, help='Dedicated local launcher state; never use the repository')
    parser.add_argument('--reviewed-sha256', help='Exact approved old global-script hash; never a general force flag')
    parser.add_argument('--restore', metavar='TRANSACTION', help='Restore both components from a local receipt')
    parser.add_argument('--apply', action='store_true', help='Apply both; default is read-only preview')
    parser.add_argument('--desktop-action', choices=('none', 'restart'), default='none', help='Explicit one-shot graceful desktop repair; default never restarts')
    parser.add_argument('--action-id', help='Single-use 32-hex ID for this separately authorized restart')
    parser.add_argument('--startup-log-dir', type=Path, help='Explicit Codex desktop Logs directory; no auth/history files')
    parser.add_argument('--readiness-timeout', type=float, default=60, help='Bounded fresh-event observation, 0..120 seconds')
    args = parser.parse_args(argv)
    if not args.restore and (not args.codex_exe or not args.kind):
        parser.error('--codex-exe and --kind are required for configuration')
    if args.restore and (args.codex_exe or args.kind or args.proxy_port is not None or args.reviewed_sha256
                         or args.desktop_action != 'none' or args.action_id or args.startup_log_dir
                         or args.readiness_timeout != 60):
        parser.error('Restore does not accept setup-only options')
    try:
        if args.restore:
            result = restore(args.clash_dir, args.restore, state_dir=args.state_dir, apply=args.apply)
        else:
            result = configure(args.clash_dir, args.codex_exe, args.kind, state_dir=args.state_dir,
                               proxy_port=args.proxy_port, apply=args.apply, reviewed_sha256=args.reviewed_sha256,
                               desktop_action=args.desktop_action, action_id=args.action_id,
                               log_dir=args.startup_log_dir, readiness_timeout=args.readiness_timeout)
        if args.apply and args.desktop_action == 'restart':
            result['verification_complete'] = (result.get('desktop', {}).get('status') == 'started'
                                               and result.get('startup', {}).get('computer_use', {}).get('status') == 'ready')
        print(json.dumps(result, ensure_ascii=True))
        if args.apply and args.desktop_action == 'restart' and not result['verification_complete']:
            return 2
        return 0
    except ConfigurationError as error:
        print(json.dumps({'error': str(error), 'recovery': error.recovery}, ensure_ascii=True), file=sys.stderr)
    except (clash.InstallError, proxy.ProxyError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=True), file=sys.stderr)
    except (OSError, ValueError, UnicodeError):
        print('Error: local configuration operation failed; no config content or inherited environment was logged.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
