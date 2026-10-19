"""Passive evidence collection and a hard one-model-launch guard for C6."""
import hashlib
import json
import os
from pathlib import Path
import sys

AUDIT = Path('/tmp/bridge-c6-audit-1472791')


def save(name, value):
    path = AUDIT / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def audit(event, args):
    if event != 'subprocess.Popen':
        return
    argv = args[1]
    if isinstance(argv, (list, tuple)) and len(argv) > 1 and argv[1] == 'exec' and 'codex' in str(argv[0]):
        save('model-launch.json', {'argv': list(argv), 'pid': os.getpid(), 'model_retry_count': 0})


def profile(frame, event, result):
    if event != 'return' or frame.f_code.co_name != 'render_once':
        return
    if not frame.f_code.co_filename.endswith('/ai_bridge_kit/clear_writing.py'):
        return
    local = frame.f_locals
    payload = dict(result or {})
    completed = local.get('result')
    if completed is not None:
        stdout = completed.stdout
        save('model-jsonl.json', {'stdout': stdout, 'returncode': completed.returncode})
        payload['raw_jsonl_sha256'] = hashlib.sha256(stdout.encode()).hexdigest()
    payload['candidate_sha'] = 'c32b9100c673ac3c9472d52271709989438bbf99'
    save('render-result.json', payload)


sys.addaudithook(audit)
sys.setprofile(profile)
