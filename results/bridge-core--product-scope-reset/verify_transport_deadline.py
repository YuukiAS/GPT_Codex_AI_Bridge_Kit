"""Non-live C5/C6 evidence: real helper termination at controlled hang points.

Only disposable config/state roots are used. No model or network is allowed.
The production deliver_notification/_deliver-helper remain the exercised code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from ai_bridge_kit import notifier


def main() -> None:
    candidate = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    expected = os.environ.get('BRIDGE_EVIDENCE_CANDIDATE', '147279107e3811dee279a337b85febb4e6c468b8')
    assert candidate == expected
    rows = []
    with tempfile.TemporaryDirectory(prefix='bridge-deadline-proof-') as tmp:
        base = Path(tmp)
        hook = base / 'observer'
        hook.mkdir()
        # Test-only fault injection at the named transport stage, in the real
        # helper subprocess. Python's audit hook forbids every socket connect
        # and every model process; even accidental fallback cannot go live.
        (hook / 'sitecustomize.py').write_text('''
import os, sys, time
from pathlib import Path
from ai_bridge_kit import clear_writing, notifier
def no_model(*a, **kw):
    raise clear_writing.ClearWritingError('CONTROLLED_NONLIVE_NO_MODEL')
clear_writing.resolve_installed_writing_style = no_model
def guard(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise RuntimeError('NONLIVE_NETWORK_FORBIDDEN')
    if event == 'subprocess.Popen' and 'exec' in args[1]:
        raise RuntimeError('NONLIVE_MODEL_FORBIDDEN')
sys.addaudithook(guard)
def hang(stage):
    if os.environ['BRIDGE_TEST_HANG'] == stage:
        Path(os.environ['BRIDGE_TEST_HANG_MARKER']).write_text(stage)
        time.sleep(30)
class ControlledSMTP:
    def __init__(self, *args, **kwargs): hang('DNS')
    def __enter__(self): hang('SMTP_CONNECT'); return self
    def __exit__(self, *args): return False
    def starttls(self): hang('TLS')
    def login(self, *args): pass
    def send_message(self, *args):
        raise RuntimeError('NONLIVE_SEND_FORBIDDEN')
notifier.smtplib.SMTP = ControlledSMTP
''', encoding='utf-8')
        for stage in ('DNS', 'SMTP_CONNECT', 'TLS'):
            root = base / stage
            values = {
                'AI_BRIDGE_NOTIFY_SMTP_USER': 'synthetic@example.invalid',
                'AI_BRIDGE_NOTIFY_SMTP_PASSWORD': 'synthetic-not-a-credential',
                'AI_BRIDGE_NOTIFY_FROM': 'synthetic@example.invalid',
                'AI_BRIDGE_NOTIFY_TO': 'synthetic@example.invalid',
            }
            notifier.atomic_write_bytes(notifier.machine_config_path(root),
                ''.join(f'{k}={v}\n' for k, v in values.items()).encode(), mode=0o600)
            marker = root / 'hang-entered'
            child_env = dict(os.environ, PYTHONPATH=str(hook) + os.pathsep + str(Path.cwd()),
                BRIDGE_TEST_HANG=stage, BRIDGE_TEST_HANG_MARKER=str(marker))
            processes = []
            def popen(command, **kwargs):
                process = subprocess.Popen(command, env=child_env, **kwargs)
                processes.append(process)
                return process
            request = notifier.notification_request(project='synthetic', task_key='deadline-proof',
                consumer='lite', fact_class='runtime_terminal', status='EXITED_0',
                decision_authority='Runtime', summary='Synthetic bounded transport probe.',
                next_action='Continue primary work.', source_event_id=stage)
            started = time.monotonic()
            result = notifier.deliver_notification(request, repo_identity='synthetic-repo',
                config_root=root, state_root=root, deadline_seconds=1.5,
                require_ready=False, popen=popen)
            elapsed = time.monotonic() - started
            if not marker.exists():
                rows.append({'hang_stage': stage, 'status': 'FAIL',
                    'helper_entry_executed': False, 'reason': result.message,
                    'helper_exit_codes': [p.returncode for p in processes],
                    'model_invocations': 0, 'smtp_sends': 0,
                    'attempt_record_present': notifier._read_latest_attempt(
                        notifier.event_directory(result.event_key, state_root=root)) is not None})
                continue
            assert marker.read_text() == stage
            assert result.status == 'DELIVERY_UNKNOWN', result
            assert len(processes) == 1 and processes[0].poll() is not None
            assert elapsed < 5, elapsed
            rows.append({'hang_stage': stage, 'status': result.status,
                'elapsed_seconds': elapsed, 'deadline_seconds': 1.5,
                'helper_reaped': True, 'primary_continued': True,
                'model_invocations': 0, 'smtp_sends': 0})
    passed = all(row['status'] == 'DELIVERY_UNKNOWN' for row in rows)
    print(json.dumps({'candidate_sha': candidate, 'cases': rows,
        'result': 'PASS' if passed else 'FAIL'}, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
