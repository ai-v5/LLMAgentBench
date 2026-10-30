import copy
import json

import pytest

from llmagentbench.contracts import ContractError
from scripts.verify_suite_comparison import compare_completed, verified_suite


def sample():
    judge = {"requested_model": "judge", "config_sha256": "fixed", "executable_sha256": "old-cli"}
    suite = {"pack_sha256": ["pack"], "engine_sha256": "engine", "driver_sha256": "driver",
             "judge": judge, "candidates": [{"id": "old-a"}, {"id": "old-b"}]}
    record = {"case_ids": ["private-example"], "repeats": 2, "max_repair_rounds": 1,
              "timeout_seconds": 240, "check_timeout_seconds": 15, "order_seed": 42,
              "python_version": "3.12", "platform": "Windows",
              "attempts": [{"case_id": "private-example", "repeat": 0, "candidate_id": "old-a"},
                           {"case_id": "private-example", "repeat": 0, "candidate_id": "old-b"}]}
    new_suite = copy.deepcopy(suite)
    new_suite["judge"]["executable_sha256"] = "new-cli"
    new_suite["candidates"] = [
        {"id": "new-a", "requested_model": "gpt-6.1-sol", "adapter": "codex", "reasoning_effort": "max", "executable_sha256": "new-cli"},
        {"id": "new-b", "requested_model": "gpt-6-luna", "adapter": "codex", "reasoning_effort": "max", "executable_sha256": "new-cli"},
    ]
    new_record = copy.deepcopy(record)
    new_record["attempts"][0]["candidate_id"] = "new-a"
    new_record["attempts"][1]["candidate_id"] = "new-b"
    return (suite, [record]), (new_suite, [new_record])


def test_reports_cli_drift_without_private_case_details():
    before, after = sample()
    result = compare_completed(before, after, {"gpt-6.1-sol", "gpt-6-luna"})
    assert result["same_judge_configuration"] is True
    assert result["same_judge_executable"] is False
    assert "private-example" not in json.dumps(result)


@pytest.mark.parametrize("change", ["pack", "case", "budget", "order", "engine", "driver", "judge", "model", "candidate-cli"])
def test_rejects_comparability_drift(change):
    before, after = sample()
    if change == "pack":
        after[0]["pack_sha256"][0] = "other"
    elif change == "case":
        after[1][0]["case_ids"] = ["different"]
    elif change == "budget":
        after[1][0]["repeats"] = 1
    elif change == "order":
        after[1][0]["attempts"].reverse()
    elif change == "engine":
        after[0]["engine_sha256"] = "other"
    elif change == "driver":
        after[0]["driver_sha256"] = "other"
    elif change == "judge":
        after[0]["judge"]["config_sha256"] = "other"
    elif change == "model":
        after[0]["candidates"][0]["requested_model"] = "other"
    else:
        after[0]["candidates"][0]["executable_sha256"] = "other"
    with pytest.raises(ContractError):
        compare_completed(before, after, {"gpt-6.1-sol", "gpt-6-luna"})


def test_incomplete_or_duplicate_suite_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr("scripts.verify_suite_comparison.read_json", lambda _: {
        "state": "running", "completed_runs": ["one"], "pack_sha256": ["pack"]})
    with pytest.raises(ContractError):
        verified_suite(tmp_path)
    monkeypatch.setattr("scripts.verify_suite_comparison.read_json", lambda _: {
        "state": "completed", "completed_runs": ["one", "one"], "pack_sha256": ["pack", "pack"]})
    with pytest.raises(ContractError):
        verified_suite(tmp_path)


def test_verified_suite_rejects_a_run_with_wrong_frozen_identity(monkeypatch, tmp_path):
    suite = {"state": "completed", "completed_runs": ["runs/one"], "pack_sha256": ["expected"],
             "engine_sha256": "engine", "config_sha256": "config", "candidates": [], "judge": {}}
    record = {"pack_sha256": "other", "engine_sha256": "engine", "config_sha256": "config",
              "candidates": [], "judge": {}}
    monkeypatch.setattr("scripts.verify_suite_comparison.read_json", lambda _: suite)
    monkeypatch.setattr("scripts.verify_suite_comparison.load_run", lambda _: record)
    with pytest.raises(ContractError):
        verified_suite(tmp_path)
