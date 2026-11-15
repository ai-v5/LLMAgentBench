import json

import pytest

from llmagentbench.contracts import ContractError, load_pack
from llmagentbench.report import export_overall, markdown, summarize
from llmagentbench.runner import run


def make_pack(root, name, scope):
    root.mkdir()
    case = {'id': name, 'category': 'analysis', 'prompt': 'Return the synthetic value.',
            'inputs': {}, 'allowed_write_paths': [],
            'checks': [{'id': 'value', 'type': 'json_equal', 'path': ['value'], 'expected': 1}]}
    (root / 'case.json').write_text(json.dumps(case), encoding='utf-8')
    manifest = {'schema_version': 1, 'id': name, 'version': '20261115',
                'visibility': 'public', 'synthetic': True, 'purpose': 'smoke',
                'cases': ['case.json']}
    if scope is not None:
        manifest['evaluation_scope'] = scope
    (root / 'pack.json').write_text(json.dumps(manifest), encoding='utf-8')
    return load_pack(root / 'pack.json')


def config():
    return {'schema_version': 1, 'repeats': 1, 'max_repair_rounds': 0,
            'timeout_seconds': 10, 'check_timeout_seconds': 10,
            'candidates': [{'id': 'fixture', 'adapter': 'fixture', 'responses': {
                name: {'answer': {'value': 1}, 'files': []} for name in ('a', 'b')}}]}


def test_evaluation_scope_is_frozen_in_receipt_and_summary(tmp_path):
    pack = make_pack(tmp_path / 'pack', 'a', 'engineering')
    receipt = run(pack, config(), tmp_path / 'run')
    assert receipt['evaluation_scope'] == 'engineering'
    assert summarize(receipt)['evaluation_scope'] == 'engineering'
    assert '评测范围：`engineering`' in markdown(summarize(receipt))


@pytest.mark.parametrize('other_scope', ['hash', None])
def test_overall_export_rejects_mixed_or_unknown_scopes(tmp_path, other_scope):
    first = run(make_pack(tmp_path / 'a-pack', 'a', 'engineering'), config(), tmp_path / 'a-run')
    second = run(make_pack(tmp_path / 'b-pack', 'b', other_scope), config(), tmp_path / 'b-run')
    assert first['state'] == second['state'] == 'completed'
    with pytest.raises(ContractError, match='scope'):
        export_overall([tmp_path / 'a-run', tmp_path / 'b-run'], tmp_path / 'out', {'fixture': 'Fixture'})
    assert not (tmp_path / 'out').exists()


def test_overall_export_allows_matching_scopes(tmp_path):
    run(make_pack(tmp_path / 'a-pack', 'a', 'engineering'), config(), tmp_path / 'a-run')
    run(make_pack(tmp_path / 'b-pack', 'b', 'engineering'), config(), tmp_path / 'b-run')
    result = export_overall([tmp_path / 'a-run', tmp_path / 'b-run'],
                            tmp_path / 'out', {'fixture': 'Fixture'})
    assert result['case_count'] == 2


@pytest.mark.parametrize('scope', ['anything-goes', [], 1, False])
def test_unknown_scope_value_is_rejected(tmp_path, scope):
    with pytest.raises(ContractError, match='scope'):
        make_pack(tmp_path / 'bad', 'a', scope)
