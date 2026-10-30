import json
import sys
from pathlib import Path

import pytest

from llmagentbench import adapters


def stream(*items):
    return '\n'.join(json.dumps(item) for item in items) + '\n'


def clean_events():
    return [
        {'type': 'thread.started'},
        {'type': 'turn.started'},
        {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'answer'}},
        {'type': 'turn.completed', 'usage': {'input_tokens': 1, 'output_tokens': 1}},
    ]


@pytest.mark.parametrize('extra', [
    {'type': 'item.started', 'item': {'type': 'command_execution', 'command': 'synthetic-private-marker'}},
    {'type': 'item.completed', 'item': {'type': 'file_change', 'changes': 'synthetic-private-marker'}},
    {'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'arguments': 'synthetic-private-marker'}},
])
def test_audit_flags_reported_tool_activity_without_recording_payload(extra):
    result = adapters.audit_codex_items(stream(*(clean_events()[:2] + [extra] + clean_events()[2:])))
    assert result['status'] == 'tool_event_reported'
    assert 'synthetic-private-marker' not in json.dumps(result)


@pytest.mark.parametrize('events', [
    clean_events()[:-1],
    clean_events()[:2] + [{'type': 'item.completed', 'item': {'type': 'unknown'}}] + clean_events()[-1:],
    clean_events()[:2] + [{'type': 'item.started'}] + clean_events()[2:],
    clean_events() + [{'type': 'unexpected_event'}],
])
def test_audit_rejects_incomplete_or_unknown_event_stream(events):
    assert adapters.audit_codex_items(stream(*events))['status'] == 'inconclusive'


def test_audit_clean_stream_is_only_a_reported_event_observation():
    result = adapters.audit_codex_items(stream(*clean_events()))
    assert result == {'status': 'no_tool_events_reported', 'scope': 'codex_exec_reported_items'}
    assert adapters.audit_codex_items(stream(*clean_events()) + 'not-json\n')['status'] == 'inconclusive'


@pytest.mark.parametrize('events', [
    [clean_events()[0], clean_events()[1], clean_events()[3], clean_events()[2]],
    clean_events() + [{'type':'item.completed','item':{'type':'reasoning'}}],
])
def test_audit_rejects_items_after_turn_completion(events):
    assert adapters.audit_codex_items(stream(*events))['status'] == 'inconclusive'


def test_startup_warning_is_not_a_model_tool_event_but_in_turn_error_is_inconclusive():
    warning = {'type': 'item.completed', 'item': {'type': 'error', 'message': 'synthetic-private-marker'}}
    events = clean_events()
    events.insert(1, warning)
    result = adapters.audit_codex_items(stream(*events))
    assert result['status'] == 'no_tool_events_reported'
    assert 'synthetic-private-marker' not in json.dumps(result)
    events.remove(warning)
    events.insert(2, warning)
    assert adapters.audit_codex_items(stream(*events))['status'] == 'inconclusive'


@pytest.mark.parametrize('add_tool,expected', [(False, 'ok'), (True, 'error')])
def test_opt_in_audit_disables_command_tools_and_rejects_reported_use(tmp_path, monkeypatch, add_tool, expected):
    monkeypatch.setattr(adapters.shutil, 'which', lambda _: sys.executable)
    def fake_execute(argv, **kwargs):
        assert any(argv[i:i + 2] == ['--disable', 'shell_tool'] for i in range(len(argv) - 1))
        assert any(argv[i:i + 2] == ['--disable', 'unified_exec'] for i in range(len(argv) - 1))
        assert any(argv[i:i + 2] == ['--disable', 'memories'] for i in range(len(argv) - 1))
        assert 'agents.enabled=false' in argv
        Path(argv[argv.index('--output-last-message') + 1]).write_text(json.dumps({'answer': 'safe', 'files': []}))
        events = clean_events()
        if add_tool:
            events.insert(2, {'type': 'item.started', 'item': {'type': 'command_execution', 'command': 'synthetic-private-marker'}})
        return {'exit_code': 0, 'timed_out': False, 'stdout': stream(*events), 'stderr': ''}
    monkeypatch.setattr(adapters, 'execute', fake_execute)
    call = adapters.invoke({'adapter': 'codex', 'model': 'test-model', 'local_lookup_audit': 'cli_items_v1'},
                           {'case_id': 'test', 'round': 0}, tmp_path, tmp_path / 'control', 5)
    assert call['status'] == expected
    assert call['local_lookup_audit']['status'] == ('tool_event_reported' if add_tool else 'no_tool_events_reported')
    assert 'synthetic-private-marker' not in json.dumps(call)
    if add_tool:
        assert call['response'] is None


def test_https_transport_is_invocation_local_and_frozen_in_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters.shutil, 'which', lambda _: sys.executable)
    def fake_execute(argv, **kwargs):
        assert 'model_provider="bench_openai_https"' in argv
        assert 'model_providers.bench_openai_https.requires_openai_auth=true' in argv
        assert 'model_providers.bench_openai_https.supports_websockets=false' in argv
        Path(argv[argv.index('--output-last-message') + 1]).write_text(json.dumps({'answer':'ok','files':[]}))
        return {'exit_code':0,'timed_out':False,'stdout':stream(*clean_events()),'stderr':''}
    monkeypatch.setattr(adapters, 'execute', fake_execute)
    candidate = {'adapter':'codex','model':'test','local_lookup_audit':'cli_items_v1','codex_transport':'https'}
    assert adapters.invoke(candidate, {'case_id':'x','round':0}, tmp_path, tmp_path/'control', 5)['status'] == 'ok'
    assert adapters.adapter_identity(candidate)['transport'] == 'https'
