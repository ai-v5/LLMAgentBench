"""Synthetic controls for explicitly authorized aggregate-only exports."""

from copy import deepcopy
from pathlib import Path

import pytest

from llmagentbench.contracts import ContractError
from scripts import export_combined_overall as exporter


def example(monkeypatch):
    target = {"version": "20261110"}
    private_pack = {"version": "20261110", "sha256": "private-hash",
                    "manifest": {"visibility": "private", "synthetic": True},
                    "cases": [{"definition": {"id": "private-a"}}, {"definition": {"id": "private-b"}}]}
    public_row = {"label": "Model max", "assigned": 2, "first_passed": 1, "passed": 1, "failed": 1,
                  "unscored": 0, "errors": 0, "timeouts": 0, "attempt_seconds": 6.0,
                  "candidate_call_seconds": 2.0, "judge_call_seconds": 0.0, "mean_pass_seconds": 3.0}
    monkeypatch.setattr(exporter, 'compose', lambda *_: ({"case_count": 1, "candidates": [public_row]}, {}, {}))
    packs = {"target": target, "private-pack": private_pack}
    monkeypatch.setattr(exporter, 'load_pack', lambda path: packs[str(path)])
    candidate = {"id": "model-max", "adapter": "codex", "requested_model": "gpt-6.1-terra", "reasoning_effort": "max"}
    judge = {"adapter": "codex", "requested_model": "gpt-6.1-sol", "reasoning_effort": "low"}

    def attempt(case_id, repeat, outcome, first_pass):
        first = "fail" if outcome == "pass" and not first_pass else outcome
        rounds = [{"round": 0, "outcome": first, "call": {"evidence_level": "MODEL_RUN", "elapsed_seconds": 1.0}, "judge_calls": []}]
        if first != outcome:
            rounds.append({"round": 1, "outcome": outcome, "call": {"evidence_level": "MODEL_RUN", "elapsed_seconds": 1.0}, "judge_calls": []})
        return {"candidate_id": "model-max", "case_id": case_id, "repeat": repeat, "outcome": outcome,
                "first_pass": first_pass, "rounds": rounds, "elapsed_seconds": 3.0}

    private = {"visibility": "private", "synthetic": True, "pack_sha256": "private-hash", "pack_version": "20261110",
               "case_ids": ["private-a", "private-b"], "repeats": 2, "max_repair_rounds": 1,
               "candidates": [candidate], "judge": judge, "engine_sha256": "engine", "config_sha256": "config",
               "timeout_seconds": 600, "check_timeout_seconds": 15,
               "attempts": [attempt("private-a", 0, "pass", True), attempt("private-a", 1, "pass", False),
                            attempt("private-b", 0, "unscored", False), attempt("private-b", 1, "timeout", False)]}
    source = {key: deepcopy(private[key]) for key in ('candidates', 'judge', 'engine_sha256', 'config_sha256', 'timeout_seconds', 'check_timeout_seconds')}
    records = {"private-run": private, "public-run": source}
    monkeypatch.setattr(exporter, 'load_run', lambda path: records[str(path)])
    selection = {"model": "gpt-6.1-terra", "effort": "max", "repeats": 2, "max_repair_rounds": 1,
                 "sources": [{"run": "public-run", "candidate_id": "model-max"}]}
    return packs, records, selection


def run(selection, allow_private=True):
    return exporter.combined(Path('target'), selection, Path('private-pack'), Path('private-run'), allow_private=allow_private)


def test_combined_results_are_aggregate_only_and_keep_all_outcomes(monkeypatch):
    _, _, selection = example(monkeypatch)
    summary, provenance = run(selection)
    row = summary['candidates'][0]
    assert summary['case_count'] == 3 and row['assigned'] == 6
    assert summary['pack_version'] == '20261110'
    assert (row['first_passed'], row['passed'], row['failed'], row['unscored'], row['timeouts']) == (2, 3, 1, 1, 1)
    assert provenance['authorized_private_overall'] is True and provenance['private_details_exported'] is False
    assert 'private-a' not in str(summary) + str(provenance)
    assert 'private-hash' not in str(summary) + str(provenance)


def test_authorization_is_checked_before_reading_private_data(monkeypatch):
    _, _, selection = example(monkeypatch)
    monkeypatch.setattr(exporter, 'load_run', lambda _: pytest.fail('must not read a run'))
    with pytest.raises(ContractError, match='authorization'):
        run(selection, allow_private=False)


@pytest.mark.parametrize('mutation', ['visibility', 'synthetic', 'pack', 'version', 'candidate', 'budget',
                                      'engine', 'config', 'matrix', 'fixture', 'outcome'])
def test_combined_export_rejects_invalid_sources(monkeypatch, mutation):
    packs, records, selection = example(monkeypatch)
    private, source = records['private-run'], records['public-run']
    if mutation == 'visibility':
        private['visibility'] = 'public'
    elif mutation == 'synthetic':
        packs['private-pack']['manifest']['synthetic'] = False
    elif mutation == 'pack':
        private['pack_sha256'] = 'other'
    elif mutation == 'version':
        private['pack_version'] = '20261110-v2'
    elif mutation == 'candidate':
        private['candidates'][0]['requested_model'] = 'other'
    elif mutation == 'budget':
        private['repeats'] = 1
    elif mutation == 'engine':
        source['engine_sha256'] = 'other'
    elif mutation == 'config':
        source['config_sha256'] = 'other'
    elif mutation == 'matrix':
        private['attempts'].pop()
    elif mutation == 'fixture':
        private['attempts'][0]['rounds'][0]['call']['evidence_level'] = 'FIXTURE_SMOKE'
    else:
        private['attempts'][0]['first_pass'] = False
    with pytest.raises(ContractError):
        run(selection)
