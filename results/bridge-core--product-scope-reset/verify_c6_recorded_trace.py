"""Replay the single recorded C6 result without any model, network or send."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from ai_bridge_kit import clear_writing, notifier


def deny_external(event, args):
    if event == 'subprocess.Popen' or event.startswith('socket.'):
        raise AssertionError('recorded-trace verification forbids external effects')


sys.addaudithook(deny_external)
root = Path(__file__).parent / 'c32b910'
record = json.loads((root / 'C6_LIVE_RAW_EVIDENCE.json').read_text())
sha = 'c32b9100c673ac3c9472d52271709989438bbf99'
assert record['candidate_sha'] == sha
data = record['evidence']
render = data['render-result.json']
raw = data['model-jsonl.json']
assert render['candidate_sha'] == data['delivery-started.json']['candidate_sha'] == sha
assert hashlib.sha256(raw['stdout'].encode()).hexdigest() == render['raw_jsonl_sha256']
events = [json.loads(line) for line in raw['stdout'].splitlines() if line.strip()]
counts = Counter(event['type'] for event in events)
assert counts['thread.started'] == counts['turn.started'] == counts['turn.completed'] == 1
assert raw['returncode'] == 0
assert len(data['attempts']) == 1
assert data['attempts'][0]['parent_attempt_id'] is None
assert data['attempts'][0]['expression_mode'] == 'DETERMINISTIC_FALLBACK'
assert render['model_invocations'] == 1 and render['model_retry_count'] == 0
assert data['receipt.json']['status'] == 'SMTP_ACCEPTED'
assert data['delivery-result.json']['result']['status'] == 'SMTP_ACCEPTED'
assert data['delivery-result.json']['elapsed_seconds'] < 120
assert render['text'] == notifier.render_auto_plain(data['request.json'])
try:
    clear_writing._parse_jsonl(raw['stdout'], render['plugin']['skills'])
except clear_writing.ClearWritingError as exc:
    parser_failure = str(exc)
else:
    raise AssertionError('missing skill consumption must not become PASS')
assert parser_failure == 'CODEX_SKILL_CONSUMPTION_UNPROVEN: writing-fidelity,chinese-prose'
message = [event['item']['text'] for event in events
           if event.get('item', {}).get('type') == 'agent_message'][-1]
assert '不代表目标已完成' in message
try:
    clear_writing.fidelity_check(notifier.expression_facts(data['request.json']), message)
except clear_writing.ClearWritingError as exc:
    secondary_failure = str(exc)
else:
    raise AssertionError('the frozen fidelity false positive was not reproduced')
assert secondary_failure == 'CLEAR_WRITING_CONCLUSION_STRENGTHENED'
print(json.dumps({
    'candidate_sha': sha,
    'verification': 'PASS_REPRODUCED_RECORDED_FAILURE',
    'c6_live_gate': 'FAIL_SKILL_CONSUMPTION_UNPROVEN',
    'parser_failure': parser_failure,
    'secondary_offline_fidelity_failure': secondary_failure,
    'secondary_failure_input_is_original_negative_caveat': True,
    'event_counts': dict(counts),
    'raw_jsonl_sha256': render['raw_jsonl_sha256'],
    'model_invocations_in_this_offline_replay': 0,
    'smtp_sends_in_this_offline_replay': 0,
    'recorded_live_model_invocations': 1,
    'recorded_live_smtp_accepted_deliveries': 1,
    'recorded_live_automatic_retry_count': 0,
    'deterministic_fallback_equals_production_renderer': True,
}, ensure_ascii=False, indent=2))
