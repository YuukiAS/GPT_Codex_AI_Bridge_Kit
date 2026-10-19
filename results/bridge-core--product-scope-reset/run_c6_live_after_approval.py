"""Run exactly one production automatic delivery from the frozen candidate."""
from dataclasses import asdict
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import time

from ai_bridge_kit import __version__, notifier

REPO = Path('/overflow/htzhu/mingcheng_new/GPT_Codex_AI_Bridge_Kit')
AUDIT = Path('/tmp/bridge-c6-audit-1472791')
SHA = 'c32b9100c673ac3c9472d52271709989438bbf99'
subprocess.run(['git', 'merge-base', '--is-ancestor', SHA, 'HEAD'], cwd=REPO, check=True)
subprocess.run(['git', 'diff', '--exit-code', SHA, '--', 'ai_bridge_kit', 'templates', 'tests', 'README.md', 'QUICKSTART.md', 'AGENTS.md', 'CHANGELOG.md', 'pyproject.toml', '.github'], cwd=REPO, check=True)
assert not os.environ.get('AI_BRIDGE_STATE_HOME')
assert os.environ.get('CODEX_HOME') == '/users/a/e/aereinh/.codex'
assert __version__ == importlib.metadata.version('gpt-codex-ai-bridge-kit') == '0.11.0'
assert not (AUDIT / 'delivery-started.json').exists()
readiness = notifier.require_notifier_ready()
config = notifier.notifier_env()
assert config['AI_BRIDGE_NOTIFY_SMTP_USER'] == 'humc2013@gmail.com'
assert config['AI_BRIDGE_NOTIFY_FROM'] == '1155246312@link.cuhk.edu.hk'
assert config['AI_BRIDGE_NOTIFY_TO'] == '1155246312@link.cuhk.edu.hk'
request = notifier.notification_request(
    project='Bridge Kit', task_key='bridge-core--product-scope-reset',
    consumer='persistent', fact_class='runtime_progress', status='running',
    decision_authority='Runtime',
    summary='这是合成通知，用于验证中文表达；不代表目标已完成。',
    next_action='等待独立终审。', eta='UNKNOWN', version='0.11.0',
    source_event_id='frozen-candidate-clear-writing-live-gate',
    runtime_id='clear-writing-canary', recipient_override='',
)
notifier.write_json(AUDIT / 'request.json', request)
notifier.write_json(AUDIT / 'delivery-started.json', {'candidate_sha': SHA, 'started_at': notifier.utc_now(), 'config_digest': readiness['config_digest']})
started = time.monotonic()
result = notifier.deliver_notification(request, repo_identity='YuukiAS/GPT_Codex_AI_Bridge_Kit@' + SHA)
report = {'candidate_sha': SHA, 'result': asdict(result), 'elapsed_seconds': time.monotonic() - started}
notifier.write_json(AUDIT / 'delivery-result.json', report)
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if result.status == 'SMTP_ACCEPTED' else 1)
