import copy

import pytest

from llmagentbench.contracts import ContractError
from scripts import export_public_token_usage
from scripts.export_public_token_usage import summarize_token_usage


def record():
    return {
        "state": "completed", "visibility": "public", "synthetic": True,
        "run_id": "synthetic", "receipt_sha256": "abc", "pack_sha256": "pack",
        "engine_sha256": "engine", "config_sha256": "config", "judge": None,
        "case_ids": ["example"], "repeats": 1,
        "candidates": [{"id": "candidate", "adapter": "codex"}],
        "attempts": [{"candidate_id": "candidate", "outcome": "pass", "first_pass": True, "rounds": [
            {"call": {"evidence_level": "MODEL_RUN", "elapsed_seconds": 2.0, "usage": {"output_tokens": 10}}},
            {"call": {"evidence_level": "MODEL_RUN", "elapsed_seconds": 3.0, "usage": {"output_tokens": 15}}},
        ]}],
    }


def test_token_totals_count_all_candidate_calls_and_not_judges():
    data = record()
    data["attempts"][0]["rounds"][0]["judge_calls"] = [{"usage": {"output_tokens": 99999}}]
    row = summarize_token_usage(data)["candidates"][0]
    assert (row["output_tokens"], row["candidate_call_seconds"], row["candidate_calls"], row["usage_calls"]) == (25, 5, 2, 2)


@pytest.mark.parametrize("patch", [{"state": "running"}, {"visibility": "private"}, {"synthetic": False}])
def test_token_export_rejects_nonpublic_or_incomplete_records(patch):
    data = record()
    data.update(patch)
    with pytest.raises(ContractError):
        summarize_token_usage(data)


@pytest.mark.parametrize("invalid", [None, -1, 2.5, True])
def test_missing_or_invalid_token_usage_is_not_partially_reported(invalid):
    data = record()
    data["attempts"][0]["rounds"][1]["call"]["usage"]["output_tokens"] = invalid
    row = summarize_token_usage(data)["candidates"][0]
    assert row["candidate_call_seconds"] == 5
    assert row["usage_calls"] == 1
    assert row["output_tokens"] is None


def test_fixture_telemetry_is_not_reported_as_a_model_measurement():
    data = record()
    data["attempts"][0]["rounds"][0]["call"]["evidence_level"] = "FIXTURE_SMOKE"
    row = summarize_token_usage(data)["candidates"][0]
    assert row["evidence_level"] == "FIXTURE_SMOKE"
    assert row["output_tokens"] is None


def test_dsh_uses_its_output_token_field():
    data = record()
    data["candidates"][0]["adapter"] = "dsh"
    data["attempts"][0]["rounds"][0]["call"]["usage"] = {"outputTokens": 40}
    data["attempts"][0]["rounds"][1]["call"]["usage"] = {"outputTokens": 5}
    assert summarize_token_usage(data)["candidates"][0]["output_tokens"] == 45


def test_kimi_uses_its_wire_output_token_field():
    data = record()
    data["candidates"][0]["adapter"] = "kimi"
    data["attempts"][0]["rounds"][0]["call"]["usage"] = {"output": 40}
    data["attempts"][0]["rounds"][1]["call"]["usage"] = {"output": 5}
    assert summarize_token_usage(data)["candidates"][0]["output_tokens"] == 45


def test_invalid_duration_does_not_produce_a_rate():
    data = record()
    data["attempts"][0]["rounds"][0]["call"]["elapsed_seconds"] = float("nan")
    with pytest.raises(ContractError):
        summarize_token_usage(data)


def test_export_rejects_private_without_writing(monkeypatch, tmp_path):
    data = record()
    data["visibility"] = "private"
    monkeypatch.setattr(export_public_token_usage, "load_run", lambda _: data)
    monkeypatch.setattr(export_public_token_usage, "read_json", lambda _: {})
    destination = tmp_path / "tokens.json"
    with pytest.raises(ContractError):
        export_public_token_usage.export_usage([tmp_path], tmp_path / "summary", destination)
    assert not destination.exists()


def test_export_does_not_replace_existing_result(monkeypatch, tmp_path):
    monkeypatch.setattr(export_public_token_usage, "load_run", lambda _: record())
    monkeypatch.setattr(export_public_token_usage, "read_json", lambda _: public_summary())
    destination = tmp_path / "tokens.json"
    destination.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_public_token_usage.export_usage([tmp_path], tmp_path / "summary", destination)
    assert destination.read_text(encoding="utf-8") == "preserve"


def public_summary():
    return {"case_count": 1, "repeats": 1,
            "candidates": [{"label": "Candidate", "assigned": 1, "first_passed": 1, "passed": 1,
                            "failed": 0, "unscored": 0, "errors": 0, "timeouts": 0, "candidate_call_seconds": 5}]}


def test_combined_aggregate_is_bound_to_public_summary():
    result = export_public_token_usage.summarize_combined([record()], public_summary())
    assert result["candidates"][0]["label"] == "Candidate"
    assert result["candidates"][0]["output_tokens"] == 25
    assert result["source_receipt_sha256"] == ["abc"]
    wrong = public_summary()
    wrong["candidates"][0]["candidate_call_seconds"] += 1
    with pytest.raises(ContractError):
        export_public_token_usage.summarize_combined([record()], wrong)
    wrong = public_summary()
    wrong["candidates"][0]["passed"] = 0
    with pytest.raises(ContractError):
        export_public_token_usage.summarize_combined([record()], wrong)


def test_combined_aggregate_rejects_duplicates_and_mismatched_identity():
    first = record()
    second = copy.deepcopy(first)
    with pytest.raises(ContractError, match="Duplicate"):
        export_public_token_usage.summarize_combined([first, second], public_summary())
    second["receipt_sha256"] = "def"
    second["pack_sha256"] = "pack-2"
    second["config_sha256"] = "different"
    with pytest.raises(ContractError, match="identities"):
        export_public_token_usage.summarize_combined([first, second], public_summary())
