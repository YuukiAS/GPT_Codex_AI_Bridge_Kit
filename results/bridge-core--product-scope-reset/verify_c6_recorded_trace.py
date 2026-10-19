"""Replay the saved C6 response through repaired production code, never live."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from ai_bridge_kit import clear_writing, notifier


def guard(event, args):
    if event.startswith('socket.'):
        raise AssertionError('offline replay forbids network')
    if event == 'subprocess.Popen' and list(args[1])[1:] != ['plugin', 'list', '--json']:
        raise AssertionError('only read-only plugin inventory is permitted')


candidate = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
sys.addaudithook(guard)
root = Path(__file__).parent / 'c32b910'
record = json.loads((root / 'C6_LIVE_RAW_EVIDENCE.json').read_text())
data = record['evidence']
raw = json.loads((root / 'C6_MODEL_JSONL.json').read_text())
assert raw == data['model-jsonl.json'] and raw['returncode'] == 0
digest = hashlib.sha256(raw['stdout'].encode()).hexdigest()
assert digest == data['render-result.json']['raw_jsonl_sha256']
events = [json.loads(line) for line in raw['stdout'].splitlines() if line.strip()]
counts = Counter(event['type'] for event in events)
assert counts['thread.started'] == counts['turn.started'] == counts['turn.completed'] == 1
recorded_response_uses = []


def recorded_runner(command, **kwargs):
    if command[1:] == ['plugin', 'list', '--json']:
        return subprocess.run(command, **kwargs)
    assert command[1:3] == ['exec', '--ephemeral']
    assert '--json' in command and command[command.index('--sandbox') + 1] == 'read-only'
    assert not recorded_response_uses
    for name in clear_writing.REQUIRED_SKILLS:
        assert f'${name}' in kwargs['input']
    recorded_response_uses.append(True)
    return SimpleNamespace(returncode=raw['returncode'], stdout=raw['stdout'], stderr='')


with tempfile.TemporaryDirectory(prefix='bridge-c6-offline-') as temporary:
    result = clear_writing.render_once(
        notifier.expression_facts(data['request.json']),
        fallback_text=notifier.render_auto_plain(data['request.json']),
        codex_bin='/users/a/e/aereinh/bin/codex',
        state_root=Path(temporary), runner=recorded_runner,
    )
assert result['mode'] == 'NORMAL_WRITING_STYLE', result
assert result['failure'] == '' and result['model_retry_count'] == 0
assert '不代表目标已完成' in result['text']
assert len(recorded_response_uses) == 1
print(json.dumps({
    'candidate_sha': candidate,
    'source_live_candidate_sha': record['candidate_sha'],
    'result': 'PASS_OFFLINE_REPLAY_NOT_LIVE_ACCEPTANCE',
    'render_result': result,
    'raw_jsonl_sha256': digest,
    'recorded_response_uses': 1,
    'real_model_invocations': 0,
    'real_smtp_sends': 0,
    'new_candidate_c6_live_status': 'NOT_RUN',
}, ensure_ascii=False, indent=2))
