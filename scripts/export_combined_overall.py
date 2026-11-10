"""Explicitly export aggregate counts from verified public and private runs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from llmagentbench.contracts import ContractError, load_pack, read_json
from llmagentbench.runner import load_run
from scripts.compose_public_reused import compose


def combined(target_path: Path, selection: dict, private_pack_path: Path,
             private_run_path: Path, *, allow_private: bool = False) -> tuple[dict, dict]:
    if not allow_private:
        raise ContractError("Private aggregate export requires explicit authorization")
    public, _, _ = compose(target_path, selection)
    target = load_pack(target_path)
    pack = load_pack(private_pack_path)
    record = load_run(private_run_path)
    if (pack["manifest"]["visibility"] != "private" or pack["manifest"]["synthetic"] is not True
            or record["visibility"] != "private" or record["synthetic"] is not True):
        raise ContractError("The additional run must use a private synthetic pack")
    if (record["pack_sha256"] != pack["sha256"]
            or record["case_ids"] != [entry["definition"]["id"] for entry in pack["cases"]]
            or pack["version"] != target["version"] or record.get("pack_version") != pack["version"]):
        raise ContractError("Private run and current pack do not match")
    if (record["repeats"] != selection["repeats"]
            or record["max_repair_rounds"] != selection["max_repair_rounds"]
            or len(record["candidates"]) != 1):
        raise ContractError("Private run budget or candidate count differs")
    candidate = record["candidates"][0]
    if (candidate["adapter"] != "codex" or candidate["requested_model"] != selection["model"]
            or candidate["reasoning_effort"] != selection["effort"]):
        raise ContractError("Private run candidate identity differs")
    matched_source = False
    for source in selection["sources"]:
        source_run = load_run(Path(source["run"]))
        candidates = [c for c in source_run["candidates"] if c["id"] == source["candidate_id"]]
        if (len(candidates) == 1 and candidates[0] == candidate
                and source_run["judge"] == record["judge"]
                and source_run["engine_sha256"] == record["engine_sha256"]
                and source_run["config_sha256"] == record["config_sha256"]
                and source_run["timeout_seconds"] == record["timeout_seconds"]
                and source_run["check_timeout_seconds"] == record["check_timeout_seconds"]):
            matched_source = True
    if not matched_source:
        raise ContractError("No public source matches the private run conditions")

    attempts = [a for a in record["attempts"] if a["candidate_id"] == candidate["id"]]
    if len(attempts) != len(pack["cases"]) * record["repeats"]:
        raise ContractError("Private attempt matrix is incomplete")
    for attempt in attempts:
        rounds = attempt["rounds"]
        if (attempt["outcome"] not in {"pass", "fail", "unscored", "error", "timeout"}
                or not rounds or len(rounds) > record["max_repair_rounds"] + 1
                or type(attempt["first_pass"]) is not bool
                or attempt["first_pass"] != (rounds[0]["outcome"] == "pass")
                or attempt["outcome"] != rounds[-1]["outcome"]
                or [rnd["round"] for rnd in rounds] != list(range(len(rounds)))):
            raise ContractError("Private attempt and round outcomes do not agree")
        for rnd in rounds:
            if any(call.get("evidence_level") != "MODEL_RUN" for call in [rnd["call"], *rnd["judge_calls"]]):
                raise ContractError("Fixture or unknown evidence cannot become a model result")

    row = public["candidates"][0]
    states = {state: sum(a["outcome"] == state for a in attempts)
              for state in ("pass", "fail", "unscored", "error", "timeout")}
    elapsed = row["attempt_seconds"] + sum(a["elapsed_seconds"] for a in attempts)
    candidate_seconds = row["candidate_call_seconds"] + sum(
        rnd["call"]["elapsed_seconds"] for a in attempts for rnd in a["rounds"])
    judge_seconds = row["judge_call_seconds"] + sum(
        call["elapsed_seconds"] for a in attempts for rnd in a["rounds"] for call in rnd["judge_calls"])
    if (not all(math.isfinite(n) and n >= 0 for n in (elapsed, candidate_seconds, judge_seconds))
            or elapsed <= 0 or candidate_seconds + judge_seconds > elapsed + 0.01):
        raise ContractError("Invalid aggregate timing")
    passed = row["passed"] + states["pass"]
    passed_elapsed = ((row["mean_pass_seconds"] or 0) * row["passed"]
                      + sum(a["elapsed_seconds"] for a in attempts if a["outcome"] == "pass"))
    assigned = row["assigned"] + len(attempts)
    result = {
        "schema_version": 2, "pack_version": target["version"],
        "case_count": public["case_count"] + len(pack["cases"]),
        "denominator": "assigned_attempts", "candidates": [{
            "label": row["label"], "evidence": "MODEL_RUN", "assigned": assigned,
            "first_passed": row["first_passed"] + sum(a["first_pass"] for a in attempts),
            "passed": passed, "failed": row["failed"] + states["fail"],
            "unscored": row["unscored"] + states["unscored"],
            "errors": row["errors"] + states["error"], "timeouts": row["timeouts"] + states["timeout"],
            "attempt_seconds": elapsed, "candidate_call_seconds": candidate_seconds,
            "judge_call_seconds": judge_seconds, "mean_attempt_seconds": elapsed / assigned,
            "mean_pass_seconds": passed_elapsed / passed if passed else None,
            "effective_passes_per_hour": passed * 3600 / elapsed,
        }],
    }
    provenance = {"schema_version": 1, "authorized_private_overall": True,
                  "private_details_exported": False, "assigned_attempts_verified": True,
                  "denominator": "assigned_attempts", "requested_models": [selection["model"]]}
    return result, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-pack", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--private-pack", type=Path, required=True)
    parser.add_argument("--private-run", type=Path, required=True)
    parser.add_argument("--allow-private-aggregate", action="store_true")
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--provenance-out", type=Path, required=True)
    args = parser.parse_args()
    if args.summary_out.exists() or args.provenance_out.exists():
        raise ContractError("Output already exists")
    summary, provenance = combined(args.target_pack, read_json(args.selection), args.private_pack,
                                   args.private_run, allow_private=args.allow_private_aggregate)
    for path, value in ((args.summary_out, summary), (args.provenance_out, provenance)):
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")


if __name__ == "__main__":
    main()
