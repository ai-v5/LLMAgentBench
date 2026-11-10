"""Synthetic negative controls for public case-level result composition."""

from copy import deepcopy
from pathlib import Path

import pytest

from llmagentbench.contracts import ContractError
from scripts import compose_public_reused as compose_module


def example(monkeypatch):
    def entry(case_id):
        return {"definition": {"id": case_id, "checks": [{"expected": 0}]}, "script_hashes": {"verify.py": "abc"}}

    cases = [entry("a"), entry("b")]
    pack = {"manifest": {"visibility": "public", "synthetic": True}, "cases": cases,
            "sha256": "pack-hash", "version": "20261110"}
    candidate = {"id": "terra", "adapter": "codex", "requested_model": "gpt-6.1-terra",
                 "reasoning_effort": "max", "executable_sha256": "exe"}

    def attempt(case_id, repeat, outcome, first_pass):
        call = {"evidence_level": "MODEL_RUN", "elapsed_seconds": 1.0, "usage": {"output_tokens": 5}}
        rounds = [{"round": 0, "outcome": outcome, "call": call, "judge_calls": []}]
        if outcome == "pass" and not first_pass:
            rounds[0]["outcome"] = "fail"
            rounds.append({"round": 1, "outcome": "pass", "call": deepcopy(call), "judge_calls": []})
        return {"candidate_id": "terra", "case_id": case_id, "repeat": repeat, "outcome": outcome,
                "first_pass": first_pass, "elapsed_seconds": 3.0,
                "rounds": rounds}

    record = {"visibility": "public", "synthetic": True, "pack_sha256": "pack-hash", "case_ids": ["a", "b"],
              "repeats": 2, "max_repair_rounds": 1, "receipt_sha256": "receipt", "candidates": [candidate],
              "judge": {"adapter": "codex", "requested_model": "gpt-6.1-sol", "reasoning_effort": "low"},
              "engine_sha256": "engine", "config_sha256": "config", "timeout_seconds": 240, "created_at": "test",
              "attempts": [attempt("a", 0, "pass", True), attempt("a", 1, "fail", False),
                           attempt("b", 0, "unscored", False), attempt("b", 1, "pass", False)]}
    packs = {"target": deepcopy(pack), "source": deepcopy(pack)}
    records = {"run": record}
    monkeypatch.setattr(compose_module, "load_pack", lambda path: packs[str(path)])
    monkeypatch.setattr(compose_module, "load_run", lambda path: records[str(path)])
    selection = {"model": "gpt-6.1-terra", "effort": "max", "label": "Terra max", "repeats": 2,
                 "max_repair_rounds": 1, "sources": [{"pack": "source", "run": "run",
                                                        "candidate_id": "terra", "cases": ["a", "b"]}]}
    return packs, records, selection


def test_reused_results_keep_all_attempts_and_partial_tokens(monkeypatch):
    _, records, selection = example(monkeypatch)
    records["run"]["attempts"][0]["rounds"][0]["call"]["usage"] = None
    summary, usage, provenance = compose_module.compose(Path("target"), selection)
    row = summary["candidates"][0]
    assert (row["assigned"], row["first_passed"], row["passed"], row["failed"], row["unscored"]) == (4, 1, 2, 1, 1)
    assert usage["candidates"][0]["output_tokens"] is None
    assert usage["candidates"][0]["usage_calls"] == 4
    assert provenance["source_receipts_verified"] is True
    assert provenance["mixed_conditions"] is False


def test_mixed_sources_retain_condition_provenance(monkeypatch):
    packs, records, selection = example(monkeypatch)
    packs["second"] = deepcopy(packs["source"])
    records["second-run"] = deepcopy(records["run"])
    records["second-run"]["receipt_sha256"] = "second-receipt"
    records["second-run"]["timeout_seconds"] = 600
    selection["sources"][0]["cases"] = ["a"]
    selection["sources"].append({"pack": "second", "run": "second-run", "candidate_id": "terra", "cases": ["b"]})
    summary, _, provenance = compose_module.compose(Path("target"), selection)
    assert summary["candidates"][0]["assigned"] == 4
    assert provenance["mixed_conditions"] is True
    assert {source["timeout_seconds"] for source in provenance["sources"]} == {240, 600}


@pytest.mark.parametrize("mutation", ["case", "checker", "pack", "private", "fixture", "candidate", "coverage", "duplicate", "missing-repeat", "bad-outcome"])
def test_reuse_rejects_mismatches(monkeypatch, mutation):
    packs, records, selection = example(monkeypatch)
    if mutation == "case":
        packs["source"]["cases"][0]["definition"]["checks"][0]["expected"] = False
    elif mutation == "checker":
        packs["source"]["cases"][0]["script_hashes"]["verify.py"] = "changed"
    elif mutation == "pack":
        records["run"]["pack_sha256"] = "changed"
    elif mutation == "private":
        records["run"]["visibility"] = "private"
    elif mutation == "fixture":
        records["run"]["attempts"][0]["rounds"][0]["call"]["evidence_level"] = "FIXTURE_SMOKE"
    elif mutation == "candidate":
        records["run"]["candidates"][0]["reasoning_effort"] = "low"
    elif mutation == "coverage":
        selection["sources"][0]["cases"] = ["a"]
    elif mutation == "duplicate":
        selection["sources"][0]["cases"] = ["a", "a"]
    elif mutation == "missing-repeat":
        records["run"]["attempts"].pop()
    else:
        records["run"]["attempts"][0]["first_pass"] = False
    with pytest.raises(ContractError):
        compose_module.compose(Path("target"), selection)


def test_actual_loader_rejects_incomplete_receipt(monkeypatch, tmp_path):
    packs, _, selection = example(monkeypatch)
    from llmagentbench.runner import load_run
    monkeypatch.setattr(compose_module, "load_run", load_run)
    run = tmp_path / "unfinished"
    run.mkdir()
    (run / "manifest.json").write_text('{"state":"running"}', encoding="utf-8")
    selection["sources"][0]["run"] = str(run)
    with pytest.raises(ContractError, match="incomplete"):
        compose_module.compose(Path("target"), selection)
