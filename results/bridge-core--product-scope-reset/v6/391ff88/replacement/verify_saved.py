"""Offline verification of observed normal-entry artifacts; no live effects."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from ai_bridge_kit import clear_writing, notifier

root=Path('/tmp/bridge-final-replacement-9ggq9knx')
repo=Path('/overflow/htzhu/mingcheng_new/GPT_Codex_AI_Bridge_Kit')
candidate='391ff889ad156540727da168fb608c5f37dbbdfc'
trace=[dict(file=p.name,**json.loads(p.read_text())) for p in sorted((root/'trace').glob('*.json'))]
def records(kind):
    return sorted([x for x in trace if x.get('kind')==kind],key=lambda x:x['wall_time'])

assert len(list((root/'trace').glob('budget-model-*.json')))==2
assert len(list((root/'trace').glob('budget-smtp-*.json')))==2
assert not records('BUDGET_EXCEEDED')
calls=records('supervisor_notification_call')
returns=records('supervisor_notification_return')
deliveries=records('delivery_call')
helpers=records('helper_return')
renders=records('render_return')
models=records('model_run_return')
emails=records('email_built')
assert len(calls)==len(returns)==len(deliveries)==len(helpers)==len(renders)==len(models)==len(emails)==2
assert [x['data']['fact_class'] for x in calls]==['runtime_start','runtime_terminal']
assert len({x['pid'] for x in calls})==1
supervisor=calls[0]['pid']
child_start=json.loads((root/'public-canary/child-start.json').read_text())
child_exit=json.loads((root/'public-canary/child-exit.json').read_text())
assert child_start['ppid']==supervisor and child_exit['pid']==child_start['pid']
assert 4.5<=child_exit['elapsed_seconds']<10
start=json.loads((root/'start-result.json').read_text())
start_output=json.loads(start['stdout'])
binding=json.loads(Path(start_output['binding_path']).read_text())
assert binding['lifecycle_state']=='TERMINAL' and binding['exit_code']==0
assert binding['child_pid']==child_start['pid']
assert len([x for x in records('process_spawn') if x['data']['argv']==binding['launch_argv']])==1
assert len([x for x in records('process_spawn') if '_supervise' in x['data']['argv']])==1
assert binding['progress_mode']=='none' and binding['progress_owner']=='none'
assert binding['progress_source_locator']=='NONE' and binding['notify']=='ON'
assert binding['recipient_override']=='' and binding['notification_cadence_minutes']==60
assert binding['launch_id']!= '23ddf3d1a9736ae4c9602ac0f114eae1efe2e0d4ed106529642eca4178ddd78b'
assert all(x['data']['caller']=='_persistent_notification' for x in deliveries)
assert all(x['pid']==supervisor for x in deliveries)
assert len({x['pid'] for x in helpers})==2
event_evidence=[]
for index,(call,ret,helper,render,model,email) in enumerate(zip(calls,returns,helpers,renders,models,emails)):
    request=ret['data']['request']
    rendered=render['data']['result']
    assert request['fact_class']==call['data']['fact_class']
    assert request['runtime_id']==binding['launch_id'] and request['consumer']=='persistent'
    assert request['decision_authority']=='Runtime' and request['recipient_override']==''
    assert rendered['mode']=='NORMAL_WRITING_STYLE' and not rendered['failure']
    assert rendered['model_invocations']==1 and rendered['model_retry_count']==0
    assert rendered['plugin']['version']=='0.5'
    assert set(rendered['plugin']['skills'])=={'writing-fidelity','response-clarity'}
    assert model['data']['returncode']==0
    parsed_text,parsed_evidence=clear_writing._parse_jsonl(model['data']['stdout'])
    assert parsed_text==rendered['text']
    assert parsed_evidence['event_counts']['thread.started']==1
    assert parsed_evidence['event_counts']['turn.started']==1
    assert parsed_evidence['event_counts']['turn.completed']==1
    clear_writing.fidelity_check(render['data']['brief'],rendered['text'])
    prompt=[x['data']['text'] for x in records('prompt') if x['pid']==render['pid']][0]
    assert '$writing-fidelity' in prompt and '$response-clarity' in prompt
    for key in ('consumer','fact_class','decision_authority','runtime_id','source_event_id','schema'):
        assert key not in prompt and key not in rendered['text']
    assert 'UNKNOWN' not in rendered['text']
    assert 'UNKNOWN' not in prompt.split('Immutable reader-facing facts: ',1)[1]
    assert email['data']['body'].strip()==rendered['text'].strip()
    assert email['data']['sender']=='1155246312@link.cuhk.edu.hk'
    assert email['data']['recipient']=='1155246312@link.cuhk.edu.hk'
    assert 'inbox delivered' not in rendered['text'].lower()
    assert '已送达收件箱' not in rendered['text']
    result=helper['data']['result']
    assert result['status']=='SMTP_ACCEPTED' and ret['data']['delivery']['status']=='SMTP_ACCEPTED'
    directory=Path(helper['data']['directory'])
    claim=json.loads((directory/'claim.json').read_text())
    attempts=[json.loads(p.read_text()) for p in (directory/'attempts').glob('*.json')]
    receipt=json.loads((directory/'receipt.json').read_text())
    assert claim['request']==request and claim['repo_identity']==str(root/'public-canary')
    assert len(attempts)==1 and attempts[0]['parent_attempt_id'] is None
    assert attempts[0]['stage']=='SMTP_ACCEPTED' and attempts[0]['expression_mode']=='NORMAL_WRITING_STYLE'
    assert receipt['attempt_id']==attempts[0]['attempt_id']
    event_evidence.append(dict(fact_class=request['fact_class'],request=request,
        supervisor_pid=supervisor,helper_pid=helper['pid'],render_result=rendered,
        model_jsonl=model['data'],prompt=prompt,email=email['data'],claim=claim,
        attempts=attempts,receipt=receipt,offline_parser_and_fidelity='PASS',
        exactly_one_turn=True,model_retry_count=0,SMTP_automatic_retry_count=0))
matching_claims=[]
for path in notifier.notifier_state_root().glob('events/*/claim.json'):
    claim=json.loads(path.read_text())
    if claim.get('repo_identity')==str(root/'public-canary'):
        matching_claims.append(claim)
assert len(matching_claims)==2
assert {x['request']['fact_class'] for x in matching_claims}=={'runtime_start','runtime_terminal'}
assert len(records('smtp_send_message_call'))==len(records('smtp_send_message_return'))==2
assert all(x['data']['result']=={} for x in records('smtp_send_message_return'))
observer=(root/'observer/sitecustomize.py').read_text()
assert not any(isinstance(node,ast.Call) and
    ((isinstance(node.func,ast.Name) and node.func.id in {'deliver_notification','render_once','send_auto_email'}) or
     (isinstance(node.func,ast.Attribute) and node.func.attr in {'deliver_notification','render_once','send_auto_email'}))
    for node in ast.walk(ast.parse(observer)))
assert not subprocess.check_output(['git','diff','--name-only',candidate,'--','.',
    ':(exclude)results',':(exclude).gitignore'],cwd=repo,text=True).strip()
assert hashlib.sha256((repo/'.gitignore').read_bytes()).hexdigest()=='6c5827da670763f9d295187f04ed652baa2f4f4cf2e80432c529400cc6ea2ae7'
ready=notifier.require_notifier_ready()
assert ready['config_digest']==start['notifier_readiness']['config_digest']
assert ready['mode']==0o600 and ready['status']=='VALID'
old=Path('/users/a/e/aereinh/.ai-bridge/persistent-run/runs/76639a289969316fd7b419c88249b351f26833fe288efd0277c10ba281355ae9.json')
old_binding=json.loads(old.read_text())
assert old_binding['lifecycle_state']=='START_REQUESTED' and 'exit_code' not in old_binding
payload=dict(candidate_sha=candidate,result='PASS',binding=binding,raw_trace=trace,
    start_result=start,child_start=child_start,child_exit=child_exit,events=event_evidence,
    actual_counts=dict(replacement_canary=1,primary_children=1,supervisors=1,logical_notifications=2,
                      model_calls=2,Gmail_SMTP_attempts=2,model_retries=0,SMTP_retries=0,send_test=0),
    no_third_notification=True,production_source_unchanged=True,user_gitignore_unchanged=True,
    notifier_ready=ready,old_invalid_binding_preserved=old_binding,
    observer_passive_AST_check='PASS',observer_smoke=json.loads((root/'smoke-result.json').read_text()),
    fixture_files={n:(root/n).read_text() for n in ['observer/sitecustomize.py','probe.py','start_once.py',
        'smoke.py','public-canary/GOAL.md','public-canary/child.py']})
print(json.dumps(payload,ensure_ascii=False,indent=2))
