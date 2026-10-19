"""C5 normal CLI/API probes using disposable synthetic machine state only."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from ai_bridge_kit import notifier


def main() -> None:
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='bridge-c5-normal-') as tmp:
        base = Path(tmp)
        machine = base / 'machine'
        repo_a, repo_b = base / 'repo-a', base / 'repo-b'
        for repo in (repo_a, repo_b):
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        values = {
            'AI_BRIDGE_NOTIFY_SMTP_USER': 'synthetic@example.invalid',
            'AI_BRIDGE_NOTIFY_SMTP_PASSWORD': 'synthetic-not-a-credential',
            'AI_BRIDGE_NOTIFY_FROM': 'synthetic@example.invalid',
            'AI_BRIDGE_NOTIFY_TO': 'synthetic-recipient@example.invalid',
            'AI_BRIDGE_NOTIFY_SUBJECT_PREFIX': '[synthetic]',
        }
        legacy = repo_a / '.ai-bridge/private/notifier.env'
        payload = ''.join(f'{k}={v}\n' for k, v in values.items()).encode()
        notifier.atomic_write_bytes(legacy, payload)
        env = dict(os.environ, AI_BRIDGE_STATE_HOME=str(machine), PYTHONPATH=str(Path.cwd()))
        cli = [sys.executable, '-m', 'ai_bridge_kit.bridge_cli']
        def command(args, *, cwd=repo_a, active_env=env):
            return subprocess.run(cli + args, cwd=cwd, env=active_env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first = command(['notifier', 'migrate-legacy', '--project', str(repo_a)])
        second = command(['notifier', 'migrate-legacy', '--project', str(repo_a)])
        assert first.returncode == second.returncode == 0
        assert first.stdout.startswith('MIGRATED:')
        assert second.stdout.startswith('NOOP_ALREADY_MIGRATED:')
        changed = payload.replace(b'synthetic-recipient@', b'different-recipient@')
        notifier.atomic_write_bytes(legacy, changed)
        conflict = command(['notifier', 'migrate-legacy', '--project', str(repo_a)])
        assert conflict.returncode == 1 and conflict.stdout.startswith('MACHINE_CONFIG_CONFLICT:')
        assert notifier.machine_config_path(machine).read_bytes() == payload
        assert legacy.read_bytes() == changed
        # Give every production override a conflicting value. Both unrelated
        # repo CLIs must still report exactly the same file/digest/mode.
        bad_env = dict(env, **{key: 'wrong@example.invalid' for key in values})
        statuses = [json.loads(command(['notifier', 'status'], cwd=repo, active_env=bad_env).stdout)
            for repo in (repo_a, repo_b)]
        assert all(s['status'] == 'VALID' and s['mode'] == 0o600 for s in statuses)
        assert statuses[0]['config_digest'] == statuses[1]['config_digest'] == notifier.redacted_config_digest(values)
        assert notifier.notifier_env(config_root=machine) == values
        hook = base / 'hook'
        hook.mkdir()
        (hook / 'sitecustomize.py').write_text('''
import os, sys
from pathlib import Path
from ai_bridge_kit import notifier, clear_writing
def no_model(*args, **kwargs):
    raise clear_writing.ClearWritingError('NONLIVE_NO_MODEL')
clear_writing.resolve_installed_writing_style = no_model
def guard(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise RuntimeError('NONLIVE_NETWORK_FORBIDDEN')
    if event == 'subprocess.Popen' and 'exec' in args[1]:
        raise RuntimeError('NONLIVE_MODEL_FORBIDDEN')
sys.addaudithook(guard)
class SyntheticSMTP:
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def starttls(self): pass
    def login(self, *args): pass
    def send_message(self, message):
        if os.environ.get('BRIDGE_TEST_FAIL_TRANSPORT') == 'yes':
            raise RuntimeError('controlled synthetic transport failure')
        with Path(os.environ['BRIDGE_TEST_SEND_RECORD']).open('a') as handle:
            handle.write('synthetic acceptance\\n')
notifier.smtplib.SMTP = SyntheticSMTP
''', encoding='utf-8')
        send_record = base / 'synthetic-acceptances'
        child_env = dict(env, PYTHONPATH=str(hook) + os.pathsep + str(Path.cwd()),
            BRIDGE_TEST_SEND_RECORD=str(send_record))
        def popen(argv, **kwargs):
            return subprocess.Popen(argv, env=child_env, **kwargs)
        request = notifier.notification_request(project='synthetic', task_key='same-task',
            consumer='lite', fact_class='runtime_terminal', status='EXITED_0',
            decision_authority='Runtime', summary='Synthetic runtime fact only.',
            next_action='Inspect completion separately.', source_event_id='same-source')
        def deliver(identity):
            return notifier.deliver_notification(request, repo_identity=identity,
                config_root=machine, state_root=machine, require_ready=False, popen=popen)
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = list(pool.map(deliver, ['repo-a', 'repo-a']))
        assert sum(r.status == 'SMTP_ACCEPTED' for r in concurrent) == 1
        assert all(r.status in {'SMTP_ACCEPTED', 'duplicate', 'in_progress_or_requires_retry'} for r in concurrent)
        other = deliver('repo-b')
        assert other.status == 'SMTP_ACCEPTED'
        assert other.event_key != concurrent[0].event_key
        child_env['BRIDGE_TEST_FAIL_TRANSPORT'] = 'yes'
        failed = deliver('repo-for-explicit-retry')
        assert failed.status == 'FAILED'
        parent = notifier._read_latest_attempt(notifier.event_directory(failed.event_key, state_root=machine))
        child_env.pop('BRIDGE_TEST_FAIL_TRANSPORT')
        retry = notifier.retry_event(failed.event_key, config_root=machine, state_root=machine, popen=popen)
        latest = notifier._read_latest_attempt(notifier.event_directory(failed.event_key, state_root=machine))
        assert retry.status == 'SMTP_ACCEPTED'
        assert latest['parent_attempt_id'] == parent['attempt_id']
        assert latest['model_invocations'] == 0
        assert len(send_record.read_text().splitlines()) == 3
        print(json.dumps({'candidate_sha': sha, 'result': 'PASS',
            'normal_cli_migration': ['MIGRATED', 'NOOP_ALREADY_MIGRATED', 'MACHINE_CONFIG_CONFLICT'],
            'legacy_retained': True, 'conflict_no_overwrite': True,
            'two_unrelated_repos_share_single_machine_config': True,
            'conflicting_process_overrides_ignored': True, 'mode': '0600',
            'concurrent_single_repo_acceptances': 1, 'cross_repo_event_keys_differ': True,
            'explicit_retry_parent_lineage': True, 'model_invocations': 0,
            'real_smtp_sends': 0, 'synthetic_transport_acceptances': 3}, indent=2))


if __name__ == '__main__':
    main()
