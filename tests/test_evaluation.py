from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from llmagentbench import adapters
from llmagentbench.contracts import ContractError, load_config, load_pack, safe_path, write_json
from llmagentbench.graders import grade
from llmagentbench.process import child_env, execute
from llmagentbench.report import export_public, markdown, summarize
from llmagentbench.runner import load_run, run
from tests.fixtures import BAD, GOOD, JUDGE, demo_config

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "examples/public/pack.json"


def test_real_before_red_for_patch(tmp_path):
    pack = load_pack(PACK)
    entry = next(e for e in pack["cases"] if e["definition"]["id"] == "patch")
    case = entry["definition"]
    for name, content in case["inputs"].items():
        (tmp_path / name).write_text(content)
    checks, _ = grade(case, entry["root"], BAD["patch"], tmp_path, tmp_path, demo_config())
    assert checks[0]["status"] == "fail"


@pytest.mark.parametrize("body", ["raise SystemExit(0)\n", "import os\nos._exit(0)\n"])
def test_candidate_cannot_bypass_verifier_with_success_exit(tmp_path, body):
    pack = load_pack(PACK)
    entry = next(e for e in pack["cases"] if e["definition"]["id"] == "patch")
    case = entry["definition"]
    for name, content in case["inputs"].items():
        (tmp_path / name).write_text(content)
    (tmp_path / "calc.py").write_text(body)
    checks, _ = grade(case, entry["root"], {"answer": "fixed", "files": []}, tmp_path, tmp_path, demo_config())
    assert checks[0]["status"] == "fail"


@pytest.fixture
def completed(tmp_path):
    return run(load_pack(PACK), demo_config(), tmp_path / "run")


def test_full_smoke_and_repair_are_not_best_of_n(completed):
    rows = {r["candidate_id"]: r for r in summarize(completed)["candidates"]}
    assert len(completed["attempts"]) == 24
    assert rows["fixture-good"]["first_pass_rate"] == 1
    assert rows["fixture-bad"]["strict_success_rate"] == 0
    assert rows["fixture-repair"]["first_pass_rate"] == 0
    assert rows["fixture-repair"]["strict_success_rate"] == 1
    assert rows["fixture-repair"]["assigned"] == 8
    assert all(r["evidence_level"] == "FIXTURE_SMOKE" for r in rows.values())
    assert all(r["human_minutes"] is None and r["total_cost_usd"] is None for r in rows.values())


def test_receipts_are_not_overwritten(tmp_path):
    destination = tmp_path / "occupied"
    destination.mkdir()
    (destination / "keep.txt").write_text("owned")
    with pytest.raises(ContractError):
        run(load_pack(PACK), demo_config(), destination)
    assert (destination / "keep.txt").read_text() == "owned"


def test_receipt_integrity_detects_changed_round(completed, tmp_path):
    root = tmp_path / "run"
    assert load_run(root)["state"] == "completed"
    receipt = next(root.glob("attempts/*/round-*/receipt.json"))
    value = json.loads(receipt.read_text())
    value["outcome"] = "invented"
    write_json(receipt, value)
    with pytest.raises(ContractError):
        load_run(root)


def test_missing_attempt_cannot_be_reported_as_completed(completed, tmp_path):
    root = tmp_path / "run"
    completed["attempts"].pop()
    write_json(root / "manifest.json", completed)
    with pytest.raises(ContractError):
        load_run(root)


def test_private_results_cannot_enter_public_checkout():
    pack = load_pack(PACK)
    pack["manifest"]["visibility"] = "private"
    with pytest.raises(ContractError):
        run(pack, demo_config(), ROOT / ".bench-runs/forbidden-private")


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", "x\\y", ".git/config", "x/../../escape", ""])
def test_path_escape_is_rejected(tmp_path, name):
    with pytest.raises(ContractError):
        safe_path(tmp_path, name)


def test_candidate_cannot_modify_protected_note(tmp_path):
    config = demo_config()
    config["candidates"] = [{"id": "bad-write", "adapter": "fixture", "responses": {**GOOD, "patch": {"answer": "fixed", "files": [{"path": "NOTICE.txt", "content": "overwritten"}]}}}]
    record = run(load_pack(PACK), config, tmp_path / "run")
    attempted = [a for a in record["attempts"] if a["case_id"] == "patch"]
    assert all(a["outcome"] == "fail" and len(a["rounds"]) == 1 for a in attempted)


def test_large_numeric_answer_is_a_failure_and_does_not_abort_matrix(tmp_path):
    config = demo_config()
    config["repeats"] = 1
    config["max_repair_rounds"] = 0
    huge = copy.deepcopy(GOOD)
    huge["roofline"]["answer"]["compute_seconds"] = 10 ** 400
    config["candidates"] = [
        {"id": "huge", "adapter": "fixture", "responses": huge},
        {"id": "good", "adapter": "fixture", "responses": GOOD},
    ]
    record = run(load_pack(PACK), config, tmp_path / "run")
    assert record["state"] == "completed"
    assert len(record["attempts"]) == 8
    assert next(a for a in record["attempts"] if a["candidate_id"] == "huge" and a["case_id"] == "roofline")["outcome"] == "fail"
    assert next(a for a in record["attempts"] if a["candidate_id"] == "good" and a["case_id"] == "roofline")["outcome"] == "pass"


def test_unavailable_judge_remains_unscored(tmp_path):
    config = demo_config()
    config["candidates"] = config["candidates"][:1]
    config.pop("judge")
    record = run(load_pack(PACK), config, tmp_path / "run")
    assert all(a["outcome"] == "unscored" for a in record["attempts"] if a["case_id"] == "explanation")
    assert summarize(record)["candidates"][0]["strict_success_rate"] == 0.75


def test_invented_judge_citation_cannot_pass(tmp_path):
    config = demo_config()
    config["candidates"] = config["candidates"][:1]
    config["judge"] = copy.deepcopy(JUDGE)
    config["judge"]["responses"]["explanation.rubric"]["answer"]["evidence"][0]["quote"] = "This text does not exist."
    record = run(load_pack(PACK), config, tmp_path / "run")
    assert all(a["outcome"] == "unscored" for a in record["attempts"] if a["case_id"] == "explanation")


def test_private_export_and_running_export_are_rejected(completed, tmp_path):
    for patch in ({"visibility": "private"}, {"synthetic": False}, {"state": "running"}):
        with pytest.raises(ContractError):
            export_public({**completed, **patch}, tmp_path / "export")
    assert not (tmp_path / "export").exists()


def test_public_export_has_no_raw_answers_paths_or_session_logs(completed, tmp_path):
    result = export_public(completed, tmp_path / "export")
    text = json.dumps(result)
    assert "attempts" not in result
    assert "NOTICE.txt" not in text
    assert "workspace" not in text
    assert "run.patch.json" not in text
    assert "FIXTURE_SMOKE" in text


def test_report_explicitly_labels_synthetic_and_non_synthetic_runs(completed):
    public = summarize(completed)
    private = summarize({**completed, "visibility": "private", "synthetic": False, "purpose": "benchmark"})
    assert "合成输入" in markdown(public)
    assert "非合成输入" in markdown(private)


def test_check_script_is_part_of_pack_identity(tmp_path):
    import shutil
    shutil.copytree(ROOT / "examples/public", tmp_path / "pack")
    before = load_pack(tmp_path / "pack/pack.json")["sha256"]
    path = tmp_path / "pack/patch/verify_patch.py"
    path.write_text(path.read_text() + "\n# evaluator revision\n")
    assert load_pack(tmp_path / "pack/pack.json")["sha256"] != before


def test_changed_check_script_is_not_scored_under_old_pack_hash(tmp_path):
    import shutil
    shutil.copytree(ROOT / "examples/public", tmp_path / "pack")
    pack = load_pack(tmp_path / "pack/pack.json")
    script = tmp_path / "pack/patch/verify_patch.py"
    script.write_text("pass\n")
    config = demo_config()
    config["repeats"] = 1
    config["candidates"] = config["candidates"][:1]
    record = run(pack, config, tmp_path / "run")
    patch = next(a for a in record["attempts"] if a["case_id"] == "patch")
    assert patch["outcome"] == "unscored"
    assert any(c["reason"] == "grader_changed_since_load" for c in patch["rounds"][0]["checks"])


def test_engine_change_invalidates_run_instead_of_exporting_mixed_results(tmp_path, monkeypatch):
    import llmagentbench.runner as runner
    calls = iter(["initial"] + ["changed"] * 100)
    monkeypatch.setattr(runner, "engine_digest", lambda: next(calls))
    config = demo_config()
    config["repeats"] = 1
    config["candidates"] = config["candidates"][:1]
    with pytest.raises(ContractError):
        run(load_pack(PACK), config, tmp_path / "run")
    record = json.loads((tmp_path / "run/manifest.json").read_text(encoding="utf-8"))
    assert record["state"] == "invalidated"
    with pytest.raises(ContractError):
        load_run(tmp_path / "run")


def test_transient_identity_drift_cannot_return_to_completed(tmp_path, monkeypatch):
    import llmagentbench.runner as runner
    checks = iter(["baseline", "baseline", "baseline", "baseline", "changed"] + ["baseline"] * 50)
    monkeypatch.setattr(runner, "engine_digest", lambda: next(checks))
    pack = load_pack(PACK)
    pack["cases"] = [entry for entry in pack["cases"] if entry["definition"]["id"] == "roofline"]
    config = demo_config()
    config["repeats"] = 1
    config["max_repair_rounds"] = 0
    config["candidates"] = config["candidates"][:1]
    with pytest.raises(ContractError):
        run(pack, config, tmp_path / "run")
    record = json.loads((tmp_path / "run/manifest.json").read_text(encoding="utf-8"))
    assert record["state"] == "invalidated"


@pytest.mark.parametrize("value", [0, -1, True, 100])
def test_bad_repeat_budget_fails_before_execution(tmp_path, value):
    config = demo_config()
    config["repeats"] = value
    write_json(tmp_path / "config.json", config)
    with pytest.raises(ContractError):
        load_config(tmp_path / "config.json")


def test_other_adapters_are_explicitly_out_of_scope(tmp_path):
    config = demo_config()
    config["candidates"][0]["adapter"] = "openai_compatible"
    write_json(tmp_path / "config.json", config)
    with pytest.raises(ContractError):
        load_config(tmp_path / "config.json")


def test_boolean_expected_value_is_not_a_number(tmp_path):
    import shutil
    shutil.copytree(ROOT / "examples/public", tmp_path / "pack")
    path = tmp_path / "pack/roofline/case.json"
    case = json.loads(path.read_text(encoding="utf-8"))
    case["checks"][0]["expected"] = True
    write_json(path, case)
    with pytest.raises(ContractError):
        load_pack(tmp_path / "pack/pack.json")


def test_child_environment_excludes_unrelated_credentials(monkeypatch):
    monkeypatch.setenv("BENCH_TEST_CREDENTIAL", "synthetic-placeholder")
    assert "BENCH_TEST_CREDENTIAL" not in child_env()
    assert child_env(["BENCH_TEST_CREDENTIAL"])["BENCH_TEST_CREDENTIAL"] == "synthetic-placeholder"
    monkeypatch.setenv("DSH_HOME", "synthetic-home")
    assert child_env()["DSH_HOME"] == "synthetic-home"


def test_timeout_terminates_owned_process(tmp_path):
    result = execute([sys.executable, "-c", "import time;time.sleep(20)"], cwd=tmp_path, stdin="", timeout=0.15)
    assert result["timed_out"]
    assert result["exit_code"] is not None


def test_codex_is_noninteractive_read_only_and_schema_bound(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters.shutil, "which", lambda _: sys.executable)
    def fake_execute(argv, **kwargs):
        assert "--ignore-user-config" in argv and "--ephemeral" in argv
        assert argv[argv.index("--sandbox") + 1] == "read-only"
        assert "expected" not in kwargs["stdin"]
        Path(argv[argv.index("--output-last-message") + 1]).write_text(json.dumps({"answer": "{\"ok\":true}", "files": []}))
        return {"exit_code": 0, "timed_out": False, "stdout": '{"type":"turn.completed","usage":{"input_tokens":2,"output_tokens":3}}\n', "stderr": ""}
    monkeypatch.setattr(adapters, "execute", fake_execute)
    call = adapters.invoke({"adapter": "codex", "model": "test-model"}, {"case_id": "test", "round": 0}, tmp_path, tmp_path / "control", 5)
    assert call["status"] == "ok"
    assert call["response"]["answer"] == {"ok": True}
    assert call["usage"]["output_tokens"] == 3
    assert call["observed_model"] is None


@pytest.mark.parametrize("reason,exit_code,expected", [("completed", 0, "ok"), ("error", 0, "error"), ("completed", 1, "error")])
def test_dsh_requires_committed_completion(tmp_path, monkeypatch, reason, exit_code, expected):
    monkeypatch.setenv("BENCH_DSH_LAUNCHER", json.dumps([sys.executable]))
    def fake_execute(argv, **kwargs):
        assert "--session-id" not in argv
        assert "--profile" in argv and "--patch" in argv
        patch = json.loads(Path(argv[argv.index("--patch") + 1]).read_text())
        assert patch[0]["config"]["model"] == "test-model"
        assert patch[1]["config"]["mode"] == "read-only"
        events = [{"type": "session", "sessionId": "synthetic-session"},
                  {"type": "status", "phase": "turn_end", "reason": {"kind": reason}},
                  {"type": "final", "text": json.dumps({"answer": "done", "files": []})}]
        return {"exit_code": exit_code, "timed_out": False, "stdout": "\n".join(json.dumps(e) for e in events), "stderr": ""}
    monkeypatch.setattr(adapters, "execute", fake_execute)
    call = adapters.invoke({"adapter": "dsh", "provider": "test", "model": "test-model"}, {"case_id": "test", "round": 0}, tmp_path, tmp_path / "control", 5)
    assert call["status"] == expected


@pytest.mark.parametrize("final,expected", [
    ('```json\n{"answer":"done","files":[]}\n```', "ok"),
    ('prefix\n```json\n{"answer":"done","files":[]}\n```', "error"),
])
def test_dsh_accepts_only_a_single_complete_json_fence(tmp_path, monkeypatch, final, expected):
    monkeypatch.setenv("BENCH_DSH_LAUNCHER", json.dumps([sys.executable]))
    def fake_execute(argv, **kwargs):
        events = [{"type": "session", "sessionId": "synthetic-session"},
                  {"type": "status", "phase": "turn_end", "reason": {"kind": "completed"}},
                  {"type": "final", "text": final}]
        return {"exit_code": 0, "timed_out": False, "stdout": "\n".join(json.dumps(e) for e in events), "stderr": ""}
    monkeypatch.setattr(adapters, "execute", fake_execute)
    call = adapters.invoke({"adapter": "dsh", "provider": "test", "model": "test-model"}, {"case_id": "test", "round": 0}, tmp_path, tmp_path / "control", 5)
    assert call["status"] == expected
