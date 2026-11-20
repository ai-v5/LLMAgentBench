import json
from pathlib import Path

import pytest

from llmagentbench.contracts import ContractError, load_pack, validate_case
from llmagentbench.graders import grade


ROOT = Path(__file__).resolve().parents[1]


def test_explanation_judge_reads_output_file_and_checks_citations(tmp_path, monkeypatch):
    from llmagentbench import graders

    entry = next(e for e in load_pack(ROOT / 'pack.json')['cases'] if e['definition']['id'] == 'explanation')
    case = entry['definition']
    answer = {'conclusion': 'OOM，无计时样本，性能未知，无授权不重试。',
              'evidence_status': 'UNAVAILABLE', 'latency_ms': None}
    (tmp_path / 'answer.json').write_text(json.dumps(answer, ensure_ascii=False), encoding='utf-8')
    captured = []

    def judge(_judge, payload, *_args):
        captured.append(payload['candidate_answer'])
        return {'status': 'ok', 'response': {'answer': {'verdict': True, 'reason': 'ok',
                'evidence': [{'source': 'answer', 'quote': quote[0]}]}, 'files': []}}

    monkeypatch.setattr(graders, 'invoke', judge)
    config = {'judge': {'adapter': 'fixture'}, 'timeout_seconds': 10, 'check_timeout_seconds': 10}
    for name in ('control1', 'control2', 'control3'):
        (tmp_path / name).mkdir()
    quote = ['OOM']
    checks, _ = grade(case, entry['root'], {'answer': '文件已生成', 'files': []}, tmp_path, tmp_path / 'control1', config)
    assert checks[-1]['status'] == 'pass'
    assert json.loads(captured[0]) == answer
    quote[0] = 'invented citation'
    checks, _ = grade(case, entry['root'], {'answer': 'invented citation', 'files': []}, tmp_path, tmp_path / 'control2', config)
    assert checks[-1]['status'] == 'unknown'
    assert checks[-1]['reason'] == 'invalid_judge_evidence'
    answer['latency_ms'] = 10
    (tmp_path / 'answer.json').write_text(json.dumps(answer), encoding='utf-8')
    checks, calls = grade(case, entry['root'], {'answer': '文件已生成', 'files': []}, tmp_path, tmp_path / 'control3', config)
    assert checks[0]['status'] == 'fail' and not calls


@pytest.mark.parametrize('name', ['../secret', 'receipt.txt', 'other.json'])
def test_judge_answer_file_must_be_a_new_allowed_path(tmp_path, name):
    entry = next(e for e in load_pack(ROOT / 'pack.json')['cases'] if e['definition']['id'] == 'explanation')
    case = entry['definition']
    case['checks'][-1]['answer_file'] = name
    with pytest.raises(ContractError):
        validate_case(case, entry['root'])


def test_patch_workspace_positive_and_negative_controls(tmp_path):
    entry = next(e for e in load_pack(ROOT / 'pack.json')['cases'] if e['definition']['id'] == 'patch')
    case = entry['definition']
    for name, content in case['inputs'].items():
        (tmp_path / name).write_text(content, encoding='utf-8')
    config = {'check_timeout_seconds': 10}
    response = {'answer': 'done', 'files': []}
    checks, _ = grade(case, entry['root'], response, tmp_path, tmp_path, config)
    assert checks[0]['status'] == 'fail'
    (tmp_path / 'calc.py').write_text('def per_item_us(total_us, count):\n    if count is None or count <= 0:\n        return None\n    return total_us / count\n', encoding='utf-8')
    checks, _ = grade(case, entry['root'], response, tmp_path, tmp_path, config)
    assert checks[0]['status'] == 'pass'
