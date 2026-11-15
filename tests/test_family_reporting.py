import json

import pytest

from llmagentbench.contracts import ContractError, load_pack
from llmagentbench.report import markdown, summarize
from llmagentbench import runner
from llmagentbench.runner import load_run, run


def build_pack(root, families):
    root.mkdir()
    for name in ('a', 'b', 'c'):
        case = {'id': name, 'category': 'analysis', 'prompt': 'Return the value.',
                'inputs': {}, 'allowed_write_paths': [],
                'checks': [{'id': 'value', 'type': 'json_equal', 'path': ['value'], 'expected': 1}]}
        (root / f'{name}.json').write_text(json.dumps(case), encoding='utf-8')
    manifest = {'schema_version': 1, 'id': 'families', 'version': '20261115',
                'visibility': 'public', 'synthetic': True, 'purpose': 'smoke',
                'case_families': families, 'cases': ['a.json', 'b.json', 'c.json']}
    (root / 'pack.json').write_text(json.dumps(manifest), encoding='utf-8')
    return load_pack(root / 'pack.json')


def test_family_macro_prevents_repeated_family_from_dominating(tmp_path):
    pack = build_pack(tmp_path / 'pack', {'a': 'coding', 'b': 'coding', 'c': 'diagnosis'})
    cfg = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
           'timeout_seconds': 10, 'check_timeout_seconds': 10, 'candidates': [
               {'id': 'fixture', 'adapter': 'fixture', 'responses': {
                   'a': {'answer': {'value': 1}, 'files': []},
                   'b': {'answer': {'value': 1}, 'files': []},
                   'c': {'answer': {'value': 0}, 'files': []}}}]}
    record = run(pack, cfg, tmp_path / 'run')
    assert load_run(tmp_path / 'run')['case_families'] == pack['manifest']['case_families']
    summary = summarize(record)
    row = summary['candidates'][0]
    assert row['strict_success_rate'] == pytest.approx(2 / 3)
    assert row['family_macro_success_rate'] == pytest.approx(1 / 2)
    assert row['family_macro_scored_accuracy'] == pytest.approx(1 / 2)
    assert row['by_family']['coding']['assigned'] == 2
    assert row['by_family']['diagnosis']['outcomes']['fail'] == 1
    assert '题族等权' in markdown(summary)


def test_unscored_family_does_not_produce_macro_scored_accuracy(tmp_path, monkeypatch):
    pack = build_pack(tmp_path / 'pack', {'a': 'coding', 'b': 'coding', 'c': 'diagnosis'})
    cfg = {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
           'timeout_seconds': 10, 'check_timeout_seconds': 10, 'candidates': [
               {'id': 'fixture', 'adapter': 'fixture', 'responses': {}}]}
    def fake_invoke(candidate, payload, workspace, control, timeout):
        status = 'error' if payload['case_id'] == 'c' else 'ok'
        return {'status': status, 'response': None if status == 'error' else {'answer': {'value': 1}, 'files': []},
                'evidence_level': 'FIXTURE_SMOKE', 'elapsed_seconds': 0, 'error': 'synthetic' if status == 'error' else None}
    monkeypatch.setattr(runner, 'invoke', fake_invoke)
    row = summarize(run(pack, cfg, tmp_path / 'run'))['candidates'][0]
    assert row['by_family']['diagnosis']['outcomes']['error'] == 1
    assert row['by_family']['diagnosis']['scored_accuracy'] is None
    assert row['family_macro_success_rate'] == pytest.approx(1 / 2)
    assert row['family_macro_scored_accuracy'] is None


@pytest.mark.parametrize('families', [{'a': 'coding'}, {'a': 'coding', 'b': 'coding', 'c': []},
                                      {'a': 'coding', 'b': 'coding', 'c': 'diagnosis', 'd': 'extra'}])
def test_family_mapping_must_cover_exact_pack_cases(tmp_path, families):
    with pytest.raises(ContractError, match='famil'):
        build_pack(tmp_path / 'pack', families)
