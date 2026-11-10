"""Compose public synthetic case results from verified, explicitly selected runs.

Each source must be a completed run of a public synthetic pack. Selected case
definitions and checker fingerprints must match the target pack exactly; run
conditions are retained in the public provenance rather than normalized away.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from llmagentbench.contracts import ContractError, canonical, load_pack, read_json, write_json
from llmagentbench.runner import load_run


def compose(target_path: Path, selection: dict) -> tuple[dict, dict, dict]:
    target = load_pack(target_path)
    manifest = target["manifest"]
    if manifest["visibility"] != "public" or manifest["synthetic"] is not True:
        raise ContractError("The target must be a public synthetic pack")
    model, effort, label = (selection.get(key) for key in ("model", "effort", "label"))
    repeats, repairs = selection.get("repeats"), selection.get("max_repair_rounds")
    if not all(isinstance(x, str) and x.strip() for x in (model, effort, label)):
        raise ContractError("A model, effort and public label are required")
    if type(repeats) is not int or repeats < 1 or type(repairs) is not int or repairs < 0:
        raise ContractError("A repeat and repair budget is required")
    sources = selection.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ContractError("Explicit sources are required")

    targets = {entry["definition"]["id"]: entry for entry in target["cases"]}
    selected, source_receipts, provenance_sources = {}, set(), []
    judge_identity = None
    for source in sources:
        pack = load_pack(Path(source["pack"]))
        record = load_run(Path(source["run"]))
        if (pack["manifest"]["visibility"] != "public" or pack["manifest"]["synthetic"] is not True
                or record["visibility"] != "public" or record["synthetic"] is not True):
            raise ContractError("Every source must be a public synthetic run")
        pack_ids = [entry["definition"]["id"] for entry in pack["cases"]]
        if record["pack_sha256"] != pack["sha256"] or record["case_ids"] != pack_ids:
            raise ContractError("Source pack does not match its run receipt")
        if record["repeats"] != repeats or record["max_repair_rounds"] != repairs:
            raise ContractError("Source repeat or repair budget differs")
        receipt = record["receipt_sha256"]
        if receipt in source_receipts:
            raise ContractError("A source receipt was selected twice")
        source_receipts.add(receipt)
        matches = [candidate for candidate in record["candidates"] if candidate["id"] == source["candidate_id"]]
        if len(matches) != 1:
            raise ContractError("Source candidate is missing or ambiguous")
        candidate = matches[0]
        if (candidate["adapter"] != "codex" or candidate["requested_model"] != model
                or candidate["reasoning_effort"] != effort):
            raise ContractError("Source candidate identity differs")
        judge = record.get("judge") or {}
        this_judge = (judge.get("adapter"), judge.get("requested_model"), judge.get("reasoning_effort"))
        if judge_identity is None:
            judge_identity = this_judge
        elif this_judge != judge_identity:
            raise ContractError("Source judge model or effort differs")
        case_ids = source.get("cases")
        if (not isinstance(case_ids, list) or not case_ids or any(not isinstance(case_id, str) for case_id in case_ids)
                or len(set(case_ids)) != len(case_ids)):
            raise ContractError("Explicit distinct source cases are required")
        entries = {entry["definition"]["id"]: entry for entry in pack["cases"]}
        for case_id in case_ids:
            if case_id in selected or case_id not in targets or case_id not in entries:
                raise ContractError("A selected case is duplicated or absent")
            old, current = entries[case_id], targets[case_id]
            if (canonical(old["definition"]) != canonical(current["definition"])
                    or old["script_hashes"] != current["script_hashes"]):
                raise ContractError("Selected case or checker differs from target")
            attempts = [item for item in record["attempts"]
                        if item["candidate_id"] == candidate["id"] and item["case_id"] == case_id]
            if len(attempts) != repeats or {item["repeat"] for item in attempts} != set(range(repeats)):
                raise ContractError("Selected case attempts are incomplete")
            for attempt in attempts:
                if attempt["outcome"] not in {"pass", "fail", "unscored", "error", "timeout"}:
                    raise ContractError("Unknown attempt outcome")
                rounds = attempt["rounds"]
                if (not rounds or len(rounds) > repairs + 1 or type(attempt["first_pass"]) is not bool
                        or attempt["first_pass"] != (rounds[0]["outcome"] == "pass")
                        or attempt["outcome"] != rounds[-1]["outcome"]
                        or [rnd["round"] for rnd in rounds] != list(range(len(rounds)))):
                    raise ContractError("Attempt and round outcomes do not agree")
                for rnd in attempt["rounds"]:
                    if any(call.get("evidence_level") != "MODEL_RUN" for call in [rnd["call"], *rnd["judge_calls"]]):
                        raise ContractError("Fixture or unknown evidence cannot become a model result")
            selected[case_id] = attempts
        provenance_sources.append({
            "selected_cases": len(case_ids), "receipt_sha256": receipt,
            "pack_sha256": record["pack_sha256"], "engine_sha256": record["engine_sha256"],
            "config_sha256": record["config_sha256"], "timeout_seconds": record["timeout_seconds"],
            "created_at": record["created_at"], "check_timeout_seconds": record.get("check_timeout_seconds"),
            "python_version": record.get("python_version"), "platform": record.get("platform"),
            "candidate_executable_sha256": candidate.get("executable_sha256"),
            "candidate_lookup_audit": candidate.get("local_lookup_audit", "not_recorded"),
            "candidate_windows_sandbox": candidate.get("windows_sandbox", "not_recorded"),
            "candidate_transport": candidate.get("transport", "not_recorded"),
            "judge_config_sha256": judge.get("config_sha256"),
            "judge_executable_sha256": judge.get("executable_sha256"),
        })

    if set(selected) != set(targets):
        raise ContractError("Selected sources do not cover the complete target pack")
    attempts = [attempt for case_id in targets for attempt in selected[case_id]]
    calls = [rnd["call"] for attempt in attempts for rnd in attempt["rounds"]]
    judge_calls = [call for attempt in attempts for rnd in attempt["rounds"] for call in rnd["judge_calls"]]
    elapsed = sum(item["elapsed_seconds"] for item in attempts)
    candidate_seconds = sum(call["elapsed_seconds"] for call in calls)
    judge_seconds = sum(call["elapsed_seconds"] for call in judge_calls)
    if (not all(math.isfinite(value) and value >= 0 for value in (elapsed, candidate_seconds, judge_seconds))
            or elapsed <= 0 or candidate_seconds + judge_seconds > elapsed + 0.01):
        raise ContractError("Invalid source timing")
    outcomes = {name: sum(item["outcome"] == name for item in attempts)
                for name in ("pass", "fail", "unscored", "error", "timeout")}
    passed_times = [item["elapsed_seconds"] for item in attempts if item["outcome"] == "pass"]
    row = {
        "label": label, "evidence": "MODEL_RUN", "assigned": len(attempts),
        "first_passed": sum(bool(item["first_pass"]) for item in attempts),
        "passed": outcomes["pass"], "failed": outcomes["fail"], "unscored": outcomes["unscored"],
        "errors": outcomes["error"], "timeouts": outcomes["timeout"],
        "attempt_seconds": elapsed, "candidate_call_seconds": candidate_seconds,
        "judge_call_seconds": judge_seconds, "mean_attempt_seconds": elapsed / len(attempts),
        "mean_pass_seconds": sum(passed_times) / len(passed_times) if passed_times else None,
        "effective_passes_per_hour": outcomes["pass"] * 3600 / elapsed,
    }
    summary = {"schema_version": 1, "case_count": len(targets), "repeats": repeats,
               "pack_version": target["version"], "candidates": [row]}
    token_counts = [(call.get("usage") or {}).get("output_tokens") for call in calls]
    valid_tokens = [n for n in token_counts if type(n) is int and n >= 0]
    usage = {
        "schema_version": 2, "case_count": len(targets), "repeats": repeats,
        "source_receipt_sha256": sorted(source_receipts),
        "candidates": [{"label": label, "adapter": "codex", "requested_model": model,
                        "reasoning_effort": effort, "evidence_level": "MODEL_RUN", "assigned": len(attempts),
                        "candidate_calls": len(calls), "usage_calls": len(valid_tokens),
                        "output_tokens": sum(valid_tokens) if calls and len(valid_tokens) == len(calls) else None,
                        "candidate_call_seconds": candidate_seconds}],
    }
    provenance = {
        "schema_version": 1, "visibility": "public", "synthetic": True,
        "source_receipts_verified": True, "target_pack_sha256": target["sha256"],
        "pack_version": target["version"], "case_count": len(targets), "repeats": repeats,
        "requested_model": model, "reasoning_effort": effort,
        "mixed_conditions": len({(s["engine_sha256"], s["config_sha256"], s["timeout_seconds"],
                                  s["candidate_executable_sha256"], s["judge_executable_sha256"],
                                  s["candidate_windows_sandbox"], s["python_version"], s["platform"])
                                 for s in provenance_sources}) > 1,
        "sources": provenance_sources,
    }
    return summary, usage, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-pack", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ContractError("Output already exists")
    summary, usage, provenance = compose(args.target_pack, read_json(args.selection))
    args.out.mkdir(parents=True)
    write_json(args.out / "summary.json", summary)
    write_json(args.out / "token-usage.json", usage)
    write_json(args.out / "provenance.json", provenance)


if __name__ == "__main__":
    main()
