"""Verify two completed suites without exporting private case details."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llmagentbench.contracts import ContractError, read_json, safe_path
from llmagentbench.runner import load_run


def verified_suite(root: Path) -> tuple[dict, list[dict]]:
    suite = read_json(root / "suite.json")
    paths = suite.get("completed_runs")
    hashes = suite.get("pack_sha256")
    if (suite.get("state") != "completed" or not isinstance(paths, list) or not paths or
            not isinstance(hashes, list) or len(paths) != len(hashes) or
            len(set(paths)) != len(paths) or len(set(hashes)) != len(hashes)):
        raise ContractError("Suite is incomplete or has duplicate runs")
    records = [load_run(safe_path(root, path)) for path in paths]
    for record, pack_hash in zip(records, hashes, strict=True):
        if (record["pack_sha256"] != pack_hash or record["engine_sha256"] != suite["engine_sha256"] or
                record["config_sha256"] != suite["config_sha256"] or record["candidates"] != suite["candidates"] or
                record["judge"] != suite["judge"]):
            raise ContractError("Run identity differs from the frozen suite")
    return suite, records


def compare_completed(old: tuple[dict, list[dict]], new: tuple[dict, list[dict]], expected_models: set[str]) -> dict:
    before, old_records = old
    after, new_records = new
    if len(old_records) != len(new_records) or before["pack_sha256"] != after["pack_sha256"]:
        raise ContractError("Case packs or pack order changed")
    if before["engine_sha256"] != after["engine_sha256"] or before["driver_sha256"] != after["driver_sha256"]:
        raise ContractError("Evaluation engine or suite driver changed")
    settings = ("repeats", "max_repair_rounds", "timeout_seconds", "check_timeout_seconds", "order_seed")
    old_slots = {candidate["id"]: index for index, candidate in enumerate(before["candidates"])}
    new_slots = {candidate["id"]: index for index, candidate in enumerate(after["candidates"])}
    for a, b in zip(old_records, new_records, strict=True):
        if a["case_ids"] != b["case_ids"] or any(a[key] != b[key] for key in settings):
            raise ContractError("Cases or budget changed")
        old_order = [(attempt["case_id"], attempt["repeat"], old_slots[attempt["candidate_id"]]) for attempt in a["attempts"]]
        new_order = [(attempt["case_id"], attempt["repeat"], new_slots[attempt["candidate_id"]]) for attempt in b["attempts"]]
        if old_order != new_order:
            raise ContractError("Assignment order changed")
    old_judge = before["judge"]
    new_judge = after["judge"]
    if not isinstance(old_judge, dict) or not isinstance(new_judge, dict):
        raise ContractError("A configured judge is required")
    comparable = lambda value: {key: item for key, item in value.items() if key != "executable_sha256"}
    if comparable(old_judge) != comparable(new_judge):
        raise ContractError("Judge configuration changed")
    candidates = after["candidates"]
    if ({c["requested_model"] for c in candidates} != expected_models or len(candidates) != len(expected_models) or
            any(c["adapter"] != "codex" or c["reasoning_effort"] != "max" for c in candidates)):
        raise ContractError("The requested candidate models were not run")
    if (not new_judge.get("executable_sha256") or any(
            c.get("executable_sha256") != new_judge["executable_sha256"] for c in candidates)):
        raise ContractError("Candidate and judge executables differ")
    return {
        "schema_version": 1,
        "same_pack_order": True,
        "same_assignment_order": True,
        "same_engine": True,
        "same_driver": True,
        "same_budget": True,
        "same_judge_configuration": True,
        "same_judge_executable": old_judge.get("executable_sha256") == new_judge.get("executable_sha256"),
        "baseline_judge_executable_sha256": old_judge.get("executable_sha256"),
        "new_judge_executable_sha256": new_judge.get("executable_sha256"),
        "engine_sha256": after["engine_sha256"],
        "driver_sha256": after["driver_sha256"],
        "same_python_and_platform": all((a["python_version"], a["platform"]) == (b["python_version"], b["platform"])
                                        for a, b in zip(old_records, new_records, strict=True)),
        "requested_models": sorted(expected_models),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expected-model", action="append", required=True)
    args = parser.parse_args()
    print(json.dumps(compare_completed(verified_suite(args.baseline), verified_suite(args.candidate), set(args.expected_model))))


if __name__ == "__main__":
    main()
