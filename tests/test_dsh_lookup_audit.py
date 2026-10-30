import json
import sys
from pathlib import Path

import pytest

from llmagentbench import adapters
from llmagentbench.contracts import ContractError, validate_adapter


def stream(events):
    return '\n'.join(json.dumps(item) for item in events)+'\n'


def clean_events():
    return [{'type':'session','sessionId':'synthetic'},
            {'type':'status','phase':'turn_start','turn':1},
            {'type':'status','phase':'step_start','turn':1,'step':1},
            {'type':'thinking','text':'synthetic'},
            {'type':'text','text':'synthetic'},
            {'type':'status','phase':'step_end','turn':1,'step':1},
            {'type':'status','phase':'turn_end','turn':1,'reason':{'kind':'completed'}},
            {'type':'final','text':json.dumps({'answer':'ok','files':[]})}]


def test_dsh_clean_stream_is_only_bounded_observation():
    result = adapters.audit_dsh_events(stream(clean_events()))
    assert result == {'status':'no_tool_events_reported','scope':'dsh_headless_json_events'}
    assert 'synthetic' not in json.dumps(result)


@pytest.mark.parametrize('events', [
    clean_events()[:-1],
    clean_events()[:2]+clean_events()[3:],
    clean_events()[:5]+clean_events()[6:],
    clean_events()+[{'type':'text','text':'after final'}],
    clean_events()[:2]+[{'type':'other'}]+clean_events()[2:],
    clean_events()[:2]+[{'type':['bad']}]+clean_events()[2:],
    clean_events()[:2]+[{'type':'thinking','truncated':True}]+clean_events()[2:],
    clean_events()[:6]+[{'type':'status','phase':'turn_end','reason':{'kind':'error'}}]+clean_events()[7:],
])
def test_dsh_audit_rejects_incomplete_unknown_or_misordered_stream(events):
    assert adapters.audit_dsh_events(stream(events))['status'] == 'inconclusive'


@pytest.mark.parametrize('index,key,value', [(2,'turn',2),(5,'step',2),(6,'turn',2)])
def test_dsh_audit_rejects_mismatched_turn_or_step(index,key,value):
    events = clean_events()
    events[index][key] = value
    assert adapters.audit_dsh_events(stream(events))['status'] == 'inconclusive'


@pytest.mark.parametrize('kind', ['tool_call','tool_result'])
def test_dsh_audit_rejects_tool_event_without_storing_arguments(kind):
    events = clean_events()
    events.insert(3,{'type':kind,'tool':'read','input':'synthetic-private-marker'})
    result = adapters.audit_dsh_events(stream(events))
    assert result['status'] == 'tool_event_reported'
    assert 'synthetic-private-marker' not in json.dumps(result)


@pytest.mark.parametrize('mode,expected', [('clean','ok'),('tool','error'),('incomplete','error')])
def test_dsh_audit_overlay_and_fail_closed(tmp_path,monkeypatch,mode,expected):
    monkeypatch.setenv('BENCH_DSH_LAUNCHER',json.dumps([sys.executable]))
    def fake_execute(argv,**kwargs):
        overlay = json.loads(Path(argv[argv.index('--patch')+1]).read_text(encoding='utf-8'))
        disabled = {row['id'] for row in overlay if row.get('disabled') is True}
        assert set(adapters.DSH_AUDIT_DISABLED_PLUGINS).issubset(disabled)
        assert 'agent-instructions' in disabled
        events = clean_events()
        if mode == 'tool':
            events.insert(3,{'type':'tool_call','input':'synthetic-private-marker'})
        elif mode == 'incomplete':
            events.insert(-1,{'type':'unexpected'})
        return {'exit_code':0,'timed_out':False,'stdout':stream(events),'stderr':''}
    monkeypatch.setattr(adapters,'execute',fake_execute)
    candidate = {'adapter':'dsh','provider':'synthetic','model':'synthetic',
                 'local_lookup_audit':'dsh_json_v1'}
    call = adapters.invoke(candidate,{'case_id':'x','round':0},tmp_path,tmp_path/'control',10)
    assert call['status'] == expected
    assert 'synthetic-private-marker' not in json.dumps(call)
    if expected == 'error':
        assert call['response'] is None


def test_audit_mode_is_bound_to_its_adapter():
    validate_adapter({'adapter':'dsh','provider':'synthetic','model':'m','local_lookup_audit':'dsh_json_v1'})
    for adapter in ({'adapter':'dsh','provider':'p','model':'m','local_lookup_audit':'cli_items_v1'},
                    {'adapter':'codex','model':'m','local_lookup_audit':'dsh_json_v1'},
                    {'adapter':'fixture','responses':{},'local_lookup_audit':None}):
        with pytest.raises(ContractError):
            validate_adapter(adapter)


def test_dsh_identity_binds_executable_and_bundle_bytes(tmp_path,monkeypatch):
    exe = tmp_path/'synthetic.exe'
    exe.write_bytes(b'executable-a')
    bundle = tmp_path/'app.asar'
    bundle.write_bytes(b'bundle-a')
    monkeypatch.setenv('BENCH_DSH_LAUNCHER',json.dumps([str(exe),str(bundle/'dsh'/'bin.js')]))
    monkeypatch.setenv('DSH_HOME',str(tmp_path/'dsh-home'))
    candidate = {'adapter':'dsh','provider':'synthetic','model':'synthetic','local_lookup_audit':'dsh_json_v1'}
    first = adapters.adapter_identity(candidate)
    assert first['local_lookup_audit'] == 'dsh_headless_json_events'
    assert first['filesystem_read_isolation'] == 'not_verified'
    assert first['executable_sha256'] and first['bundle_sha256']
    exe.write_bytes(b'executable-b')
    assert adapters.adapter_identity(candidate)['executable_sha256'] != first['executable_sha256']
    bundle.write_bytes(b'bundle-b')
    assert adapters.adapter_identity(candidate)['bundle_sha256'] != first['bundle_sha256']
