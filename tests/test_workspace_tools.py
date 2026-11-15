import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from llmagentbench import adapters, runner
from llmagentbench.contracts import ContractError, load_pack
from llmagentbench.report import export_overall, export_public, summarize


def make_pack(root, name, mode='workspace_tools'):
    root.mkdir()
    case = {'id': name, 'category': 'coding', 'prompt': 'Update result.txt.',
            'inputs': {'policy.txt': 'do not modify', 'result.txt': 'before'},
            'allowed_write_paths': ['result.txt'],
            'checks': [{'id': 'value', 'type': 'json_equal', 'path': ['value'], 'expected': 1}]}
    (root / 'case.json').write_text(json.dumps(case), encoding='utf-8')
    manifest = {'schema_version': 1, 'id': name, 'version': '20261115',
                'visibility': 'public', 'synthetic': True, 'purpose': 'smoke',
                'evaluation_scope': 'engineering', 'cases': ['case.json']}
    if mode is not None:
        manifest['invocation_mode'] = mode
    (root / 'pack.json').write_text(json.dumps(manifest), encoding='utf-8')
    return load_pack(root / 'pack.json')


def config():
    return {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
            'timeout_seconds': 10, 'check_timeout_seconds': 10,
            'candidates': [{'id': 'fixture', 'adapter': 'fixture', 'responses': {}}]}


@pytest.mark.parametrize('break_protected', [False, True])
def test_workspace_tools_grades_direct_edits_and_protects_inputs(tmp_path, monkeypatch, break_protected):
    pack = make_pack(tmp_path / 'pack', 'case')
    def fake_invoke(candidate, payload, workspace, control, timeout, *, invocation_mode):
        assert invocation_mode == 'workspace_tools'
        assert 'inputs' not in payload and sorted(payload['input_paths']) == ['policy.txt', 'result.txt']
        (workspace / 'result.txt').write_text('after', encoding='utf-8')
        (workspace / 'scratch.py').write_text('temporary work', encoding='utf-8')
        if break_protected:
            (workspace / 'policy.txt').write_text('changed', encoding='utf-8')
        return {'status': 'ok', 'response': {'answer': {'value': 1}, 'files': []},
                'evidence_level': 'FIXTURE_SMOKE', 'elapsed_seconds': 0}
    monkeypatch.setattr(runner, 'invoke', fake_invoke)
    record = runner.run(pack, config(), tmp_path / 'run')
    assert record['invocation_mode'] == 'workspace_tools'
    assert summarize(record)['invocation_mode'] == 'workspace_tools'
    assert record['attempts'][0]['outcome'] == ('fail' if break_protected else 'pass')


def test_workspace_tools_rejects_tool_disabled_lookup_audit_before_creating_run(tmp_path):
    cfg = config()
    cfg['candidates'] = [{'id': 'dsh', 'adapter': 'dsh', 'model': 'm', 'provider': 'p',
                          'local_lookup_audit': 'dsh_json_v1'}]
    with pytest.raises(ContractError, match='audit'):
        runner.run(make_pack(tmp_path / 'pack', 'case'), cfg, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()


def test_workspace_tools_dsh_preserves_tool_events_without_payloads(tmp_path, monkeypatch):
    monkeypatch.setenv('BENCH_DSH_LAUNCHER', json.dumps([sys.executable]))
    def fake_execute(argv, **kwargs):
        overlay = json.loads(Path(argv[argv.index('--patch') + 1]).read_text(encoding='utf-8'))
        sandbox = next(row['config'] for row in overlay if row['id'] == 'sandbox-policy')
        assert sandbox['mode'] == 'workspace-write'
        assert not any(row.get('id') in {'tool-web', 'tool-fs', 'tool-pwsh', 'tool-bash'}
                       and row.get('disabled') for row in overlay)
        assert 'modify files directly' in kwargs['stdin'].lower()
        events = [{'type': 'session', 'sessionId': 'synthetic'},
                  {'type': 'tool_call', 'input': 'synthetic-private-marker'},
                  {'type': 'tool_result', 'status': 'error', 'output': 'synthetic-private-marker'},
                  {'type': 'status', 'phase': 'turn_end', 'reason': {'kind': 'completed'}},
                  {'type': 'final', 'text': 'Finished.'}]
        return {'exit_code': 0, 'timed_out': False,
                'stdout': '\n'.join(json.dumps(e) for e in events), 'stderr': ''}
    monkeypatch.setattr(adapters, 'execute', fake_execute)
    call = adapters.invoke({'adapter': 'dsh', 'provider': 'p', 'model': 'm'},
                           {'case_id': 'x', 'round': 0, 'task': 'x', 'input_paths': []},
                           tmp_path, tmp_path / 'control', 10, invocation_mode='workspace_tools')
    assert call['status'] == 'ok' and call['tool_call_count'] == 1 and call['tool_error_count'] == 1
    assert call['response'] == {'answer': 'Finished.', 'files': []}
    assert 'synthetic-private-marker' not in json.dumps(call)


@pytest.mark.parametrize('answer,tool_errors,expected', [(0, 1, 'unscored'), (0, 0, 'fail'), (1, 1, 'pass')])
def test_tool_error_does_not_masquerade_as_a_scored_failure(tmp_path, monkeypatch, answer, tool_errors, expected):
    def fake_invoke(candidate, payload, workspace, control, timeout, *, invocation_mode):
        return {'status': 'ok', 'response': {'answer': {'value': answer}, 'files': []},
                'evidence_level': 'FIXTURE_SMOKE', 'elapsed_seconds': 0, 'tool_error_count': tool_errors}
    monkeypatch.setattr(runner, 'invoke', fake_invoke)
    record = runner.run(make_pack(tmp_path / 'pack', 'case'), config(), tmp_path / 'run')
    attempt = record['attempts'][0]
    assert attempt['outcome'] == expected
    if expected == 'unscored':
        uncertain = [check for check in attempt['rounds'][0]['checks'] if check['status'] == 'unknown']
        assert uncertain and uncertain[0]['original_status'] == 'fail'


def test_overall_export_rejects_mixed_invocation_modes(tmp_path, monkeypatch):
    def fake_invoke(candidate, payload, workspace, control, timeout, **kwargs):
        return {'status': 'ok', 'response': {'answer': {'value': 1}, 'files': []},
                'evidence_level': 'FIXTURE_SMOKE', 'elapsed_seconds': 0}
    monkeypatch.setattr(runner, 'invoke', fake_invoke)
    runner.run(make_pack(tmp_path / 'a-pack', 'a', None), config(), tmp_path / 'a-run')
    runner.run(make_pack(tmp_path / 'b-pack', 'b'), config(), tmp_path / 'b-run')
    with pytest.raises(ContractError, match='mode'):
        export_overall([tmp_path / 'a-run', tmp_path / 'b-run'],
                       tmp_path / 'out', {'fixture': 'Fixture'})


def test_invalid_invocation_mode_is_rejected(tmp_path):
    with pytest.raises(ContractError, match='mode'):
        make_pack(tmp_path / 'pack', 'case', 'anything')


def test_workspace_tools_rejects_formal_purpose_without_isolation(tmp_path):
    pack = make_pack(tmp_path / 'pack', 'case')
    manifest = pack['manifest']
    manifest['purpose'] = 'benchmark'
    (tmp_path / 'pack' / 'pack.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ContractError, match='candidate or smoke'):
        load_pack(tmp_path / 'pack' / 'pack.json')


def test_legacy_tool_run_without_snapshot_cannot_be_publicly_exported(tmp_path):
    record = {'state': 'completed', 'visibility': 'public', 'synthetic': True,
              'invocation_mode': 'workspace_tools'}
    with pytest.raises(ContractError, match='snapshot'):
        export_public(record, tmp_path / 'out')


def test_workspace_tools_codex_uses_workspace_and_plain_final(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters.shutil, 'which', lambda _: sys.executable)
    def fake_execute(argv, **kwargs):
        assert '--search' in argv and '--output-schema' not in argv
        assert argv[argv.index('--sandbox') + 1] == 'workspace-write'
        assert 'modify files directly' in kwargs['stdin'].lower()
        Path(argv[argv.index('--output-last-message') + 1]).write_text('Finished.', encoding='utf-8')
        return {'exit_code': 0, 'timed_out': False, 'stdout': '', 'stderr': ''}
    monkeypatch.setattr(adapters, 'execute', fake_execute)
    call = adapters.invoke({'adapter': 'codex', 'model': 'm'},
                           {'case_id': 'x', 'round': 0, 'task': 'x', 'input_paths': []},
                           tmp_path, tmp_path / 'control', 10, invocation_mode='workspace_tools')
    assert call['status'] == 'ok' and call['response'] == {'answer': 'Finished.', 'files': []}


@pytest.mark.parametrize('status,exit_code,expected', [
    ('failed', 1, 0), ('failed', 126, 1), ('failed', 127, 1), ('failed', 137, 1),
    ('failed', 9009, 1), ('failed', -1, 1), ('failed', None, 1), ('declined', None, 1),
])
def test_codex_nonzero_command_exit_is_not_a_tool_infrastructure_error(tmp_path, monkeypatch, status, exit_code, expected):
    monkeypatch.setattr(adapters.shutil, 'which', lambda _: sys.executable)

    def fake_execute(argv, **kwargs):
        Path(argv[argv.index('--output-last-message') + 1]).write_text('Finished.', encoding='utf-8')
        event = {'type': 'item.completed', 'item': {'type': 'command_execution', 'status': status,
                                                    'exit_code': exit_code}}
        return {'exit_code': 0, 'timed_out': False, 'stdout': json.dumps(event), 'stderr': ''}

    monkeypatch.setattr(adapters, 'execute', fake_execute)
    call = adapters.invoke({'adapter': 'codex', 'model': 'm'},
                           {'case_id': 'x', 'round': 0, 'task': 'x', 'input_paths': []},
                           tmp_path, tmp_path / 'control', 10, invocation_mode='workspace_tools')
    assert call['status'] == 'ok' and call['tool_error_count'] == expected


def test_failed_test_command_does_not_hide_a_failed_grade(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters.shutil, 'which', lambda _: sys.executable)

    def fake_execute(argv, **kwargs):
        Path(argv[argv.index('--output-last-message') + 1]).write_text('Wrong answer.', encoding='utf-8')
        event = {'type': 'item.completed', 'item': {'type': 'command_execution',
                                                    'status': 'failed', 'exit_code': 1}}
        return {'exit_code': 0, 'timed_out': False, 'stdout': json.dumps(event), 'stderr': ''}

    monkeypatch.setattr(adapters, 'execute', fake_execute)
    cfg = config()
    cfg['candidates'] = [{'id': 'codex', 'adapter': 'codex', 'model': 'm'}]
    record = runner.run(make_pack(tmp_path / 'pack', 'case'), cfg, tmp_path / 'run')
    assert record['attempts'][0]['outcome'] == 'fail'


@pytest.mark.parametrize('source', ['raise SystemExit(0)\n',
                                    'def matches(expected, observed):\n    raise SystemExit(0)\n'])
def test_v8_shape_checker_rejects_early_success_exit(tmp_path, source):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'shape_match.py').write_text(source, encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'examples/agent-tools/shape-match-v5/verify.py'),
                             str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0


def test_v8_shape_checker_requires_keyword_compatible_signature(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = ("def matches(*args):\n"
              "    expected, observed = args\n"
              "    return all(k in expected and observed.get(k) == expected[k] "
              "for k in ('op', 'shape', 'dtype', 'device'))\n")
    (tmp_path / 'shape_match.py').write_text(source, encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'examples/agent-tools/shape-match-v5/verify.py'),
                             str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0


def test_v8_shape_checker_detects_stateful_implementation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = ("calls = 0\n"
              "def matches(expected, observed):\n"
              "    global calls\n"
              "    calls += 1\n"
              "    if calls > 1:\n        return False\n"
              "    return all(k in expected and observed.get(k) == expected[k] "
              "for k in ('op', 'shape', 'dtype', 'device'))\n")
    (tmp_path / 'shape_match.py').write_text(source, encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'examples/agent-tools/shape-match-v5/verify.py'),
                             str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0


def test_v7_evaluator_already_rejects_early_success_exit(tmp_path):
    root = Path(__file__).resolve().parents[1]
    pack = load_pack(root / 'examples/agent-tools/pack-20261115-v7.json')
    name = 'agent-shape-match'
    pack['cases'] = [entry for entry in pack['cases'] if entry['definition']['id'] == name]
    pack['manifest']['case_families'] = {name: 'code-repair'}
    cfg = config()
    cfg['candidates'][0]['responses'] = {name: {'answer': '', 'files': [
        {'path': 'shape_match.py', 'content': 'raise SystemExit(0)\n'}]}}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert record['attempts'][0]['outcome'] == 'fail'


@pytest.mark.parametrize('preamble,lookup', [
    ("from collections import __dict__ as d\nb = d['__builtins__']\ns = b['__import__']('sys')\n", "b['getattr']"),
    ("import typing\ns = typing.sys\nb = s.modules['builtins']\n", 'b.getattr'),
    ("from typing import sys as s\nb = s.modules['builtins']\n", 'b.getattr'),
])
def test_v8_evaluator_rejects_candidate_tampering_with_checks(tmp_path, preamble, lookup):
    root = Path(__file__).resolve().parents[1]
    pack = load_pack(root / 'examples/agent-tools/pack-20261116-v8.json')
    name = 'agent-shape-match'
    pack['cases'] = [entry for entry in pack['cases'] if entry['definition']['id'] == name]
    pack['manifest']['case_families'] = {name: 'code-repair'}
    source = (preamble +
              "def matches(expected, observed):\n"
              f"    g = {lookup}({lookup}(s, '_getframe')(1), 'f_globals')\n"
              "    if 'checks' in g:\n        g['checks'].clear()\n"
              "    return len(expected) > 1\n")
    cfg = config()
    cfg['candidates'][0]['responses'] = {name: {'answer': '', 'files': [
        {'path': 'shape_match.py', 'content': source}]}}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert record['attempts'][0]['outcome'] == 'fail'


@pytest.mark.parametrize('setup', [
    "s = typing.sys\nb = s.modules['builtins']\ng = b.getattr\n",
    "op = typing.operator\nag = op.attrgetter\ns = ag('sys')(typing)\n"
    "b = ag('modules')(s)['builtins']\ng = ag('getattr')(b)\n",
])
def test_v8_evaluator_rejects_forged_checker_completion(tmp_path, setup):
    root = Path(__file__).resolve().parents[1]
    pack = load_pack(root / 'examples/agent-tools/pack-20261116-v8.json')
    name = 'agent-shape-match'
    pack['cases'] = [entry for entry in pack['cases'] if entry['definition']['id'] == name]
    pack['manifest']['case_families'] = {name: 'code-repair'}
    source = ("import typing\n"
              "def matches(*args):\n    return False\n"
              + setup +
              "payload = g(g(s, '_getframe')(1), 'f_globals')['payload']\n"
              "rows = [{'value': b.all(k in r['expected'] and k in r['observed'] and "
              "r['expected'][k] == r['observed'][k] for k in ('op', 'shape', 'dtype', 'device')), "
              "'unchanged': True} for r in payload['requests']]\n"
              "g(g(s, 'stdout'), 'write')('BENCH_SHAPE_RESULT:' + g(s, 'modules')['json'].dumps(rows) + b.chr(10))\n"
              "g(s, 'exit')(0)\n")
    cfg = config()
    cfg['candidates'][0]['responses'] = {name: {'answer': '', 'files': [
        {'path': 'shape_match.py', 'content': source}]}}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert record['attempts'][0]['outcome'] == 'fail'


@pytest.mark.parametrize('value', [
    {'isolated_tokens_per_second': 1000, 'mixed_status': 'MIXED', 'mixed_decode_tokens_per_second': 1500},
    {'isolated_tokens_per_second': 1000, 'mixed_status': 'MIXED', 'decode_tokens_per_second': 1500},
    {'windows': [{'id': 'isolated', 'isolated_tokens_per_second': 1000},
                 {'id': 'mixed', 'mixed_status': 'MIXED'}], 'mixed_tokens_per_second': 1500},
    {'windows': [{'id': 'isolated', 'isolated_tokens_per_second': 1000},
                 {'id': 'mixed', 'mixed_status': 'MIXED'}], 'tokens_per_second': 1500},
])
def test_v8_window_checker_rejects_explicit_mixed_throughput(tmp_path, value):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'window_report.json').write_text(json.dumps(value), encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'examples/agent-tools/performance-window-v3/verify.py'),
                             str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0


def test_v8_preserves_case_contracts_and_accepts_equivalent_valid_answers(tmp_path):
    root = Path(__file__).resolve().parents[1]
    previous = load_pack(root / 'examples/agent-tools/pack-20261115-v7.json')
    current = load_pack(root / 'examples/agent-tools/pack-20261116-v8.json')
    old = {entry['definition']['id']: entry for entry in previous['cases']}
    new = {entry['definition']['id']: entry for entry in current['cases']}
    assert old.keys() == new.keys()
    for case_id in old:
        if case_id == 'agent-performance-window':
            old_case, new_case = deepcopy(old[case_id]['definition']), deepcopy(new[case_id]['definition'])
            assert '顶层 tokens_per_second' in new_case.pop('prompt')
            old_case.pop('prompt')
            assert old_case == new_case
        else:
            assert old[case_id]['definition'] == new[case_id]['definition']
        assert (old[case_id]['script_hashes'] != new[case_id]['script_hashes']) == (
            case_id in {'agent-shape-match', 'agent-performance-window'})
    code = ("def matches(expected, observed):\n"
            "    try:\n"
            "        return all(observed.get(k, NotImplemented) == expected[k] "
            "for k in ('op', 'shape', 'dtype', 'device'))\n"
            "    except (KeyError, IndexError):\n        return False\n")
    (tmp_path / 'shape_match.py').write_text(code, encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'examples/agent-tools/shape-match-v5/verify.py'),
                             str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    answer = {'windows': [{'id': 'isolated', 'isolated_tokens_per_second': 1000},
                          {'id': 'mixed', 'mixed_status': 'MIXED'}], 'tokens_per_second': 1000}
    (tmp_path / 'window_report.json').write_text(json.dumps(answer), encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'examples/agent-tools/performance-window-v3/verify.py'),
                             str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('imports,annotation', [
    ('from collections.abc import Mapping\n', 'Mapping'),
    ('from typing import Mapping\n', 'Mapping'),
    ('import collections.abc\n', 'collections.abc.Mapping'),
    ('import typing as t\n', 't.Mapping'),
])
def test_v8_shape_checker_accepts_common_standard_library_imports(tmp_path, imports, annotation):
    root = Path(__file__).resolve().parents[1]
    source = (imports + f'def matches(expected: {annotation}, observed: {annotation}):\n'
              "    return all(k in expected and k in observed and expected[k] == observed[k] "
              "for k in ('op', 'shape', 'dtype', 'device'))\n")
    (tmp_path / 'shape_match.py').write_text(source, encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'examples/agent-tools/shape-match-v5/verify.py'),
                             str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_workspace_tools_identity_freezes_ca_file_without_recording_path(tmp_path, monkeypatch):
    ca_file = tmp_path / 'synthetic-ca.pem'
    ca_file.write_text('synthetic-ca-a', encoding='utf-8')
    monkeypatch.setenv('NODE_EXTRA_CA_CERTS', str(ca_file))
    candidate = {'adapter': 'fixture', 'responses': {}, 'pass_env': ['NODE_EXTRA_CA_CERTS']}
    first = adapters.adapter_identity(candidate, invocation_mode='workspace_tools')
    ca_file.write_text('synthetic-ca-b', encoding='utf-8')
    second = adapters.adapter_identity(candidate, invocation_mode='workspace_tools')
    assert first['network_ca_sha256'] != second['network_ca_sha256']
    assert str(ca_file) not in json.dumps(first)


def test_workspace_tools_dsh_identity_freezes_launcher_patch_bytes(tmp_path, monkeypatch):
    patch = tmp_path / 'catalog.json'
    patch.write_text('{"version": 1}', encoding='utf-8')
    monkeypatch.setenv('BENCH_DSH_LAUNCHER', json.dumps([sys.executable, '--patch', str(patch)]))
    monkeypatch.setenv('DSH_HOME', str(tmp_path / 'dsh-home'))
    candidate = {'adapter': 'dsh', 'provider': 'synthetic', 'model': 'synthetic'}
    first = adapters.adapter_identity(candidate, invocation_mode='workspace_tools')
    patch.write_text('{"version": 2}', encoding='utf-8')
    second = adapters.adapter_identity(candidate, invocation_mode='workspace_tools')
    assert first['launcher_patch_sha256'] != second['launcher_patch_sha256']
    assert str(patch) not in json.dumps(first)


def test_workspace_tools_freezes_and_verifies_each_round_workspace(tmp_path, monkeypatch):
    def fake_invoke(candidate, payload, workspace, control, timeout, *, invocation_mode):
        number = payload['round']
        (workspace / 'result.txt').write_text(f'round-{number}', encoding='utf-8')
        return {'status': 'ok', 'response': {'answer': {'value': number}, 'files': []},
                'evidence_level': 'FIXTURE_SMOKE', 'elapsed_seconds': 0}
    monkeypatch.setattr(runner, 'invoke', fake_invoke)
    cfg = config()
    cfg['max_repair_rounds'] = 1
    record = runner.run(make_pack(tmp_path / 'pack', 'case'), cfg, tmp_path / 'run')
    assert record['workspace_snapshot_version'] == 1
    attempt = record['attempts'][0]
    assert [item['outcome'] for item in attempt['rounds']] == ['fail', 'pass']
    attempt_root = tmp_path / 'run' / 'attempts' / attempt['id']
    for number in (0, 1):
        snap = attempt_root / f'round-{number}' / 'workspace_snapshot' / 'result.txt'
        assert snap.read_text(encoding='utf-8') == f'round-{number}'
    assert runner.load_run(tmp_path / 'run')['receipt_sha256'] == record['receipt_sha256']
    (attempt_root / 'round-0' / 'workspace_snapshot' / 'result.txt').write_text('tampered', encoding='utf-8')
    with pytest.raises(ContractError, match='snapshot'):
        runner.load_run(tmp_path / 'run')


def test_workspace_tools_grader_mutation_is_unscored(tmp_path, monkeypatch):
    def fake_invoke(candidate, payload, workspace, control, timeout, *, invocation_mode):
        (workspace / 'result.txt').write_text('candidate result', encoding='utf-8')
        return {'status': 'ok', 'response': {'answer': {'value': 1}, 'files': []},
                'evidence_level': 'FIXTURE_SMOKE', 'elapsed_seconds': 0}
    def mutating_grader(case, case_root, response, workspace, control, cfg, **kwargs):
        (workspace / 'result.txt').write_text('grader changed this', encoding='utf-8')
        return ([{'id': 'value', 'type': 'json_equal', 'status': 'pass'}], [])
    monkeypatch.setattr(runner, 'invoke', fake_invoke)
    monkeypatch.setattr(runner, 'grade', mutating_grader)
    record = runner.run(make_pack(tmp_path / 'pack', 'case'), config(), tmp_path / 'run')
    assert record['attempts'][0]['outcome'] == 'unscored'
    assert record['attempts'][0]['rounds'][0]['checks'][0]['reason'] == 'grader_changed_workspace'


def test_workspace_tools_smoke_cases_have_positive_and_negative_controls(tmp_path):
    root = Path(__file__).resolve().parents[1]
    pack = load_pack(root / 'examples/agent-tools/pack.json')
    summary = {'assigned': 6, 'passed': 1, 'failed': 1, 'errors': 1,
               'timeouts': 1, 'unscored': 1, 'missing': 1,
               'elapsed_seconds': 100, 'passes_per_hour': 36}
    decision = {'eligible': ['m6', 'm1'], 'missing': ['m5'], 'mean_ms': 3.0}
    def responses(summary_value, decision_value):
        return {'agent-result-accounting': {'answer': '', 'files': [
                    {'path': 'summary.json', 'content': json.dumps(summary_value)}]},
                'agent-measurement-triage': {'answer': '', 'files': [
                    {'path': 'decision.json', 'content': json.dumps(decision_value)}]}}
    cfg = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
           'timeout_seconds': 10, 'check_timeout_seconds': 10, 'candidates': [
               {'id': 'good', 'adapter': 'fixture', 'responses': responses(summary, decision)},
               {'id': 'bad', 'adapter': 'fixture', 'responses': responses(
                   {**summary, 'failed': 2, 'missing': 0},
                   {**decision, 'eligible': ['m1', 'm4'], 'mean_ms': 2.3})}]}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert all(a['outcome'] == ('pass' if a['candidate_id'] == 'good' else 'fail')
               for a in record['attempts'])


def test_expanded_tool_smoke_has_code_review_and_diagnosis_controls(tmp_path):
    root = Path(__file__).resolve().parents[1]
    pack = load_pack(root / 'examples/agent-tools/pack-20261115-v2.json')
    ids = {'agent-fix-metrics', 'agent-review-export', 'agent-runtime-diagnosis'}
    pack['cases'] = [entry for entry in pack['cases'] if entry['definition']['id'] in ids]
    assert {entry['definition']['id'] for entry in pack['cases']} == ids
    code = ("from math import fsum\ndef summarize(rows):\n"
            "    elapsed = fsum(row['seconds'] for row in rows)\n"
            "    passed = sum(row['status'] == 'pass' for row in rows)\n"
            "    return {'passed': passed, 'elapsed_seconds': elapsed, "
            "'passes_per_hour': passed * 3600 / elapsed if elapsed else None}\n")
    def responses(code_text, issues, status, next_check):
        return {'agent-fix-metrics': {'answer': '', 'files': [{'path': 'metrics.py', 'content': code_text}]},
                'agent-review-export': {'answer': '', 'files': [{'path': 'review.json',
                    'content': json.dumps({'issues': issues})}]},
                'agent-runtime-diagnosis': {'answer': '', 'files': [{'path': 'diagnosis.json',
                    'content': json.dumps({'status': status, 'next_check': next_check})}]}}
    cfg = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
           'timeout_seconds': 10, 'check_timeout_seconds': 10, 'candidates': [
               {'id': 'good', 'adapter': 'fixture', 'responses': responses(code,
                   ['private_case_details_exported', 'missing_assignment_denominator'],
                   'CONTAINER_DEVICE_UNAVAILABLE', 'CONTAINER_DEVICE_MAPPING')},
               {'id': 'bad', 'adapter': 'fixture', 'responses': responses(
                   code.replace("fsum(row['seconds'] for row in rows)",
                                "fsum(row['seconds'] for row in rows if row['status'] == 'pass')"),
                   ['missing_assignment_denominator'], 'DRIVER_FAILED', 'REPLACE_DRIVER')}]}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert all(a['outcome'] == ('pass' if a['candidate_id'] == 'good' else 'fail')
               for a in record['attempts'])


def test_domain_tool_smoke_has_positive_and_negative_controls(tmp_path):
    root = Path(__file__).resolve().parents[1]
    pack = load_pack(root / 'examples/agent-tools/pack-20261115-v4.json')
    ids = {'agent-shape-match', 'agent-review-cache', 'agent-performance-window', 'agent-parallel-plan'}
    pack['cases'] = [entry for entry in pack['cases'] if entry['definition']['id'] in ids]
    pack['manifest']['case_families'] = {case_id: pack['manifest']['case_families'][case_id] for case_id in ids}
    good_code = ("def matches(expected, observed):\n"
                 "    return all(k in expected and k in observed and expected[k] == observed[k] "
                 "for k in ('op', 'shape', 'dtype', 'device'))\n")
    bad_code = good_code.replace("'op', 'shape', 'dtype', 'device'", "'op', 'shape'")
    def responses(code, issues, status, tokens):
        return {
            'agent-shape-match': {'answer': '', 'files': [{'path': 'shape_match.py', 'content': code}]},
            'agent-review-cache': {'answer': '', 'files': [{'path': 'review.json',
                'content': json.dumps({'issues': issues})}]},
            'agent-performance-window': {'answer': '', 'files': [{'path': 'window_report.json',
                'content': json.dumps({'isolated_tokens_per_second': 1000, 'mixed_status': status})}]},
            'agent-parallel-plan': {'answer': '', 'files': [{'path': 'plan.json',
                'content': json.dumps({'rows': [{'id': 'a', 'nmb': 6, 'global_sequences': 48, 'unique_tokens': tokens},
                                                 {'id': 'b', 'nmb': 4, 'global_sequences': 32, 'unique_tokens': 131072}]})}]},
        }
    cfg = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
           'timeout_seconds': 10, 'check_timeout_seconds': 10, 'candidates': [
               {'id': 'good', 'adapter': 'fixture', 'responses': responses(good_code,
                   ['CACHE_IDENTITY_INCOMPLETE', 'MISSING_TREATED_AS_ZERO'], 'MIXED', 98304)},
               {'id': 'bad', 'adapter': 'fixture', 'responses': responses(bad_code,
                   ['CACHE_IDENTITY_INCOMPLETE'], 'ISOLATED', 393216)}]}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert all(a['outcome'] == ('pass' if a['candidate_id'] == 'good' else 'fail')
               for a in record['attempts'])


def test_v5_graders_accept_equivalent_valid_implementations_and_formats(tmp_path):
    root = Path(__file__).resolve().parents[1]
    before = load_pack(root / 'examples/agent-tools/pack-20261115-v4.json')
    pack = load_pack(root / 'examples/agent-tools/pack-20261115-v5.json')
    ids = {'agent-shape-match', 'agent-review-cache', 'agent-parallel-plan'}
    old = {entry['definition']['id']: entry for entry in before['cases']}
    new = {entry['definition']['id']: entry for entry in pack['cases']}
    for name in ids:
        assert old[name]['definition'] == new[name]['definition']
        assert old[name]['script_hashes'] != new[name]['script_hashes']
    pack['cases'] = [entry for entry in pack['cases'] if entry['definition']['id'] in ids]
    pack['manifest']['case_families'] = {case_id: pack['manifest']['case_families'][case_id] for case_id in ids}
    code = ("from collections.abc import Mapping\n"
            "def matches(expected: Mapping[str, object], observed: Mapping[str, object]) -> bool:\n"
            "    return all(k in expected and k in observed and expected[k] == observed[k] "
            "for k in ('op', 'shape', 'dtype', 'device'))\n")
    rows = [{'id': 'a', 'nmb': 6, 'global_sequences': 48, 'unique_tokens': 98304},
            {'id': 'b', 'nmb': 4, 'global_sequences': 32, 'unique_tokens': 131072}]
    def responses(source, issues, plan):
        return {'agent-shape-match': {'answer': '', 'files': [{'path': 'shape_match.py', 'content': source}]},
                'agent-review-cache': {'answer': '', 'files': [{'path': 'review.json',
                    'content': json.dumps({'issues': issues})}]},
                'agent-parallel-plan': {'answer': '', 'files': [{'path': 'plan.json',
                    'content': json.dumps(plan)}]}}
    cfg = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
           'timeout_seconds': 10, 'check_timeout_seconds': 10, 'candidates': [
               {'id': 'good', 'adapter': 'fixture', 'responses': responses(code,
                   [{'code': 'CACHE_IDENTITY_INCOMPLETE'}, {'id': 'MISSING_TREATED_AS_ZERO'}], rows)},
               {'id': 'bad', 'adapter': 'fixture', 'responses': responses(
                   code.replace("'op', 'shape', 'dtype', 'device'", "'op', 'shape'"),
                   [{'code': 'CACHE_IDENTITY_INCOMPLETE'}], [{**rows[0], 'unique_tokens': 1}, rows[1]])}]}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert all(a['outcome'] == ('pass' if a['candidate_id'] == 'good' else 'fail')
               for a in record['attempts'])


def test_v6_accepts_standard_exceptions_and_equivalent_window_layout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    before = load_pack(root / 'examples/agent-tools/pack-20261115-v5.json')
    pack = load_pack(root / 'examples/agent-tools/pack-20261115-v6.json')
    ids = {'agent-shape-match', 'agent-performance-window'}
    old = {entry['definition']['id']: entry for entry in before['cases']}
    new = {entry['definition']['id']: entry for entry in pack['cases']}
    for name in ids:
        assert old[name]['definition'] == new[name]['definition']
        assert old[name]['script_hashes'] != new[name]['script_hashes']
    pack['cases'] = [entry for entry in pack['cases'] if entry['definition']['id'] in ids]
    pack['manifest']['case_families'] = {case_id: pack['manifest']['case_families'][case_id] for case_id in ids}
    code = ("def matches(expected, observed):\n    try:\n"
            "        return all(expected[k] == observed[k] for k in ('op', 'shape', 'dtype', 'device'))\n"
            "    except (KeyError, IndexError):\n        return False\n")
    rows = [{'id': 'isolated', 'isolated_tokens_per_second': 1000},
            {'id': 'mixed', 'mixed_status': 'MIXED'}]
    def responses(source, windows):
        return {'agent-shape-match': {'answer': '', 'files': [{'path': 'shape_match.py', 'content': source}]},
                'agent-performance-window': {'answer': '', 'files': [{'path': 'window_report.json',
                    'content': json.dumps({'windows': windows})}]}}
    cfg = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
           'timeout_seconds': 10, 'check_timeout_seconds': 10, 'candidates': [
               {'id': 'good', 'adapter': 'fixture', 'responses': responses(code, rows)},
               {'id': 'bad', 'adapter': 'fixture', 'responses': responses(
                   code.replace("'op', 'shape', 'dtype', 'device'", "'op', 'shape'"),
                   [rows[0], {**rows[1], 'tokens_per_second': 1500}])}]}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert all(a['outcome'] == ('pass' if a['candidate_id'] == 'good' else 'fail')
               for a in record['attempts'])


def test_v7_accepts_standard_sentinels_without_weakening_shape_checks(tmp_path):
    root = Path(__file__).resolve().parents[1]
    before = load_pack(root / 'examples/agent-tools/pack-20261115-v6.json')
    pack = load_pack(root / 'examples/agent-tools/pack-20261115-v7.json')
    name = 'agent-shape-match'
    old = next(entry for entry in before['cases'] if entry['definition']['id'] == name)
    new = next(entry for entry in pack['cases'] if entry['definition']['id'] == name)
    assert old['definition'] == new['definition'] and old['script_hashes'] != new['script_hashes']
    pack['cases'] = [new]
    pack['manifest']['case_families'] = {name: 'code-repair'}
    code = ("def matches(expected, observed):\n"
            "    return all(k in expected and observed.get(k, NotImplemented) == expected[k] "
            "for k in ('op', 'shape', 'dtype', 'device'))\n")
    cfg = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
           'timeout_seconds': 10, 'check_timeout_seconds': 10, 'candidates': [
               {'id': label, 'adapter': 'fixture', 'responses': {name: {'answer': '', 'files': [
                   {'path': 'shape_match.py', 'content': source}]}}}
               for label, source in [('good', code), ('bad', code.replace("'op', 'shape', 'dtype', 'device'", "'op', 'shape'"))]]}
    record = runner.run(pack, cfg, tmp_path / 'run')
    assert {a['candidate_id']: a['outcome'] for a in record['attempts']} == {'good': 'pass', 'bad': 'fail'}
