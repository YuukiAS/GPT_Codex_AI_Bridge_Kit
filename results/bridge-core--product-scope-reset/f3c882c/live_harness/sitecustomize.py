"""Passive C6 trace collection, with hard one-model / one-send guards."""
import hashlib
import json
import os
from pathlib import Path
import sys

AUDIT = Path('/tmp/bridge-c6-audit-f3c882c')
SHA = 'f3c882c5302a1889cac62526e8f025ada0f4d1a5'


def save(name, value):
    fd = os.open(AUDIT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def audit(event, args):
    if event != 'subprocess.Popen':
        return
    argv = args[1]
    if isinstance(argv, (list, tuple)) and len(argv) > 1 and argv[1] == 'exec' and 'codex' in str(argv[0]):
        save('model-launch.json', {'argv': list(argv), 'pid': os.getpid(), 'model_retry_count': 0})


def profile(frame, event, result):
    if event == 'call' and frame.f_code.co_name == 'send_message' and frame.f_code.co_filename.endswith('/smtplib.py'):
        save('smtp-send-started.json', {'candidate_sha': SHA, 'pid': os.getpid(), 'retry': 0})
    if event != 'return' or frame.f_code.co_name != 'render_once':
        return
    if not frame.f_code.co_filename.endswith('/ai_bridge_kit/clear_writing.py'):
        return
    payload = dict(result or {})
    completed = frame.f_locals.get('result')
    if completed is not None:
        stdout = completed.stdout
        save('model-jsonl.json', {'stdout': stdout, 'returncode': completed.returncode})
        payload['raw_jsonl_sha256'] = hashlib.sha256(stdout.encode()).hexdigest()
    payload['candidate_sha'] = SHA
    save('render-result.json', payload)


sys.addaudithook(audit)
sys.setprofile(profile)
