import json
from pathlib import Path

import pytest
from llmagentbench.contracts import load_pack
from llmagentbench.runner import run

ROOT = Path(__file__).resolve().parents[1]


def test_every_engineering_case_has_positive_and_negative_controls(tmp_path):
    pack = load_pack(ROOT / 'examples/engineering/pack.json')
    controls = json.loads((ROOT / 'tests/engineering_controls.json').read_text(encoding='utf-8'))
    assert len(pack['cases']) == 8
    assert {c['definition']['topic'] for c in pack['cases']} == {'coding', 'diagnosis', 'review', 'performance'}
    assert all(sum(c['definition']['topic'] == t for c in pack['cases']) == 2 for t in ('coding', 'diagnosis', 'review', 'performance'))
    assert set(controls) == {c['definition']['id'] for c in pack['cases']}
    for entry in pack['cases']:
        case = entry['definition']
        for check in case['checks']:
            if check['type'] == 'json_equal' and isinstance(check['expected'], str):
                assert check['expected'] in case['prompt'] and '枚举' in case['prompt']
    config = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0, 'timeout_seconds': 20,
              'check_timeout_seconds': 10, 'candidates': [
                  {'id': 'positive', 'adapter': 'fixture', 'responses': {k: v['good'] for k, v in controls.items()}},
                  {'id': 'negative', 'adapter': 'fixture', 'responses': {k: v['bad'] for k, v in controls.items()}},
              ]}
    result = run(pack, config, tmp_path / 'controls')
    assert all(a['outcome'] == ('pass' if a['candidate_id'] == 'positive' else 'fail') for a in result['attempts'])


def test_code_case_rejects_filesystem_side_effects_before_execution(tmp_path):
    pack = load_pack(ROOT / 'examples/engineering/pack.json')
    case = next(c for c in pack['cases'] if c['definition']['id'] == 'quality-rate')
    pack['cases'] = [case]
    sentinel = tmp_path / 'must-not-exist'
    code = f'def summarize(rows):\n    open({str(sentinel)!r}, "w").write("x")\n    return {{}}\n'
    config = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0, 'timeout_seconds': 20,
              'check_timeout_seconds': 10, 'candidates': [{'id': 'unsafe', 'adapter': 'fixture', 'responses':
                  {'quality-rate': {'answer': 'fixed', 'files': [{'path': 'candidate.py', 'content': code}]}}}]}
    result = run(pack, config, tmp_path / 'unsafe')
    assert result['attempts'][0]['outcome'] == 'fail'
    assert not sentinel.exists()


def test_performance_case_accepts_two_decimal_rounding(tmp_path):
    pack = load_pack(ROOT / 'examples/engineering/pack.json')
    case = next(c for c in pack['cases'] if c['definition']['id'] == 'overlap-proxy')
    pack['cases'] = [case]
    response = {'answer': {'step_ms': 60, 'decode_tokens_per_s': 533.33, 'evidence': 'PROXY'}}
    config = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0, 'timeout_seconds': 20,
              'check_timeout_seconds': 10, 'candidates': [{'id': 'rounded', 'adapter': 'fixture',
                  'responses': {'overlap-proxy': response}}]}
    result = run(pack, config, tmp_path / 'rounded')
    assert result['attempts'][0]['outcome'] == 'pass'


@pytest.mark.parametrize('case_id,mutant', [
    ('quality-rate', '''def summarize(rows):
    passed = sum(1 for r in rows if r["status"] == "pass")
    elapsed = sum(r["elapsed_s"] for r in rows if r["status"] != "unscored")
    return {"passed":passed,"elapsed_s":elapsed,"passes_per_hour":passed * 3600 / elapsed if elapsed else None}
'''),
    ('native-rank-proof', None),
])
def test_coding_checker_rejects_semantic_shortcuts(tmp_path, case_id, mutant):
    pack = load_pack(ROOT / 'examples/engineering/pack.json')
    case = next(c for c in pack['cases'] if c['definition']['id'] == case_id)
    pack['cases'] = [case]
    controls = json.loads((ROOT / 'tests/engineering_controls.json').read_text(encoding='utf-8'))
    if mutant is None:
        mutant = controls[case_id]['good']['files'][0]['content'].replace(' and r["outputs"] and all(', ' and all(')
        assert mutant != controls[case_id]['good']['files'][0]['content']
    config = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0, 'timeout_seconds': 20,
              'check_timeout_seconds': 10, 'candidates': [{'id': 'mutant', 'adapter': 'fixture', 'responses':
                  {case_id: {'answer': 'fixed', 'files': [{'path': 'candidate.py', 'content': mutant}]}}}]}
    result = run(pack, config, tmp_path / 'mutant')
    assert result['attempts'][0]['outcome'] == 'fail'


def test_rank_checker_rejects_hardcoded_world_size(tmp_path):
    pack = load_pack(ROOT / 'examples/engineering/pack.json')
    pack['cases'] = [next(c for c in pack['cases'] if c['definition']['id'] == 'native-rank-proof')]
    controls = json.loads((ROOT / 'tests/engineering_controls.json').read_text(encoding='utf-8'))
    code = controls['native-rank-proof']['good']['files'][0]['content']
    mutant = code.replace('or world <= 0:', 'or world != 2:')
    assert mutant != code
    config = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0, 'timeout_seconds': 20,
              'check_timeout_seconds': 10, 'candidates': [{'id': 'mutant', 'adapter': 'fixture', 'responses':
                  {'native-rank-proof': {'answer': 'fixed', 'files': [{'path': 'candidate.py', 'content': mutant}]}}}]}
    result = run(pack, config, tmp_path / 'hardcoded')
    assert result['attempts'][0]['outcome'] == 'fail'


@pytest.mark.parametrize('operation', ['tuple', 'set_add', 'bytes', 'bytearray', 'frozenset'])
def test_rank_checker_accepts_prompt_allowed_python_operations(tmp_path, operation):
    pack = load_pack(ROOT / 'examples/engineering/pack.json')
    pack['cases'] = [next(c for c in pack['cases'] if c['definition']['id'] == 'native-rank-proof')]
    controls = json.loads((ROOT / 'tests/engineering_controls.json').read_text(encoding='utf-8'))
    code = controls['native-rank-proof']['good']['files'][0]['content']
    if operation == 'tuple':
        code = code.replace('ranks = receipt.get("ranks", [])', 'ranks = tuple(receipt.get("ranks", []))')
    elif operation == 'set_add':
        code = code.replace('if len(ranks) != world or sorted(r["rank"] for r in ranks) != list(range(world)):',
                            'seen = set()\n    for r in ranks:\n        seen.add(r["rank"])\n    if len(ranks) != world or seen != set(range(world)):')
    elif operation in {'bytes', 'bytearray'}:
        code = code.replace('ranks = receipt.get("ranks", [])',
                            f'ranks = receipt.get("ranks", [])\n    if isinstance(ranks, {operation}):\n        return False')
    else:
        code = code.replace('sorted(r["rank"] for r in ranks) != list(range(world))',
                            'frozenset(r["rank"] for r in ranks) != frozenset(range(world))')
    config = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0, 'timeout_seconds': 20,
              'check_timeout_seconds': 10, 'candidates': [{'id': 'correct', 'adapter': 'fixture', 'responses':
                  {'native-rank-proof': {'answer': 'fixed', 'files': [{'path': 'candidate.py', 'content': code}]}}}]}
    result = run(pack, config, tmp_path / operation)
    assert result['attempts'][0]['outcome'] == 'pass'
