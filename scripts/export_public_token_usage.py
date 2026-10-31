"""Export candidate-call token totals from a verified public synthetic run."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from llmagentbench.contracts import ContractError, read_json
from llmagentbench.runner import load_run


def summarize_token_usage(record: dict) -> dict:
    if record.get("state") != "completed" or record.get("visibility") != "public" or record.get("synthetic") is not True:
        raise ContractError("Only completed public synthetic runs may be exported")

    rows = []
    for candidate in record["candidates"]:
        calls = [rnd["call"] for attempt in record["attempts"]
                 if attempt["candidate_id"] == candidate["id"] for rnd in attempt["rounds"]]
        if any(call.get("evidence_level") not in {"MODEL_RUN", "FIXTURE_SMOKE"} for call in calls):
            raise ContractError("Unknown call evidence")
        evidence = "FIXTURE_SMOKE" if candidate["adapter"] == "fixture" or any(
            call["evidence_level"] == "FIXTURE_SMOKE" for call in calls
        ) else "MODEL_RUN"
        token_key = {"codex": "output_tokens", "dsh": "outputTokens", "kimi": "output"}.get(candidate["adapter"])
        seconds = []
        tokens = []
        for call in calls:
            elapsed = call.get("elapsed_seconds")
            if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
                raise ContractError("Invalid candidate call duration")
            seconds.append(elapsed)
            usage = call.get("usage")
            count = usage.get(token_key) if isinstance(usage, dict) and token_key else None
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                tokens.append(count)
        # A partial total would silently exclude failed or missing calls from the rate.
        complete = bool(calls) and len(tokens) == len(calls) and evidence == "MODEL_RUN"
        rows.append({"candidate_id": candidate["id"], "adapter": candidate["adapter"],
                     "evidence_level": evidence, "candidate_calls": len(calls),
                     "usage_calls": len(tokens), "output_tokens": sum(tokens) if complete else None,
                     "candidate_call_seconds": round(sum(seconds), 6)})
    return {"schema_version": 1, "run_id": record["run_id"],
            "source_receipt_sha256": record["receipt_sha256"], "candidates": rows}


def summarize_combined(records: list[dict], summary: dict) -> dict:
    if not records:
        raise ContractError("At least one public run is required")
    parts = [summarize_token_usage(record) for record in records]
    if len({r["receipt_sha256"] for r in records}) != len(records) or len({r["pack_sha256"] for r in records}) != len(records):
        raise ContractError("Duplicate runs or packs cannot be counted twice")
    first = records[0]
    if any(r["engine_sha256"] != first["engine_sha256"] or r["config_sha256"] != first["config_sha256"] or
           r["candidates"] != first["candidates"] or r["judge"] != first["judge"] or r["repeats"] != first["repeats"]
           for r in records):
        raise ContractError("Run identities or repeat counts differ")
    case_count = sum(len(r["case_ids"]) for r in records)
    if summary.get("case_count") != case_count or summary.get("repeats") != first["repeats"] or len(summary.get("candidates", [])) != len(first["candidates"]):
        raise ContractError("Public summary does not match the selected runs")
    rows = []
    for index, candidate in enumerate(first["candidates"]):
        items = [part["candidates"][index] for part in parts]
        summary_row = summary["candidates"][index]
        seconds = sum(item["candidate_call_seconds"] for item in items)
        attempts = [a for r in records for a in r["attempts"] if a["candidate_id"] == candidate["id"]]
        assigned = len(attempts)
        counts = {"assigned": assigned, "first_passed": sum(a["first_pass"] for a in attempts)}
        counts.update({field: sum(a["outcome"] == outcome for a in attempts) for field, outcome in
                       (("passed", "pass"), ("failed", "fail"), ("unscored", "unscored"), ("errors", "error"), ("timeouts", "timeout"))})
        if (any(summary_row.get(key) != value for key, value in counts.items()) or not isinstance(summary_row.get("label"), str) or
                abs(summary_row["candidate_call_seconds"] - seconds) > 0.001):
            raise ContractError("Public candidate summary does not match the selected runs")
        complete = all(item["output_tokens"] is not None for item in items)
        rows.append({"label": summary_row["label"], "candidate_id": candidate["id"], "adapter": candidate["adapter"],
                     "requested_model": candidate.get("requested_model"), "reasoning_effort": candidate.get("reasoning_effort"),
                     "evidence_level": "MODEL_RUN" if all(item["evidence_level"] == "MODEL_RUN" for item in items) else "FIXTURE_SMOKE",
                     "assigned": assigned, "candidate_calls": sum(item["candidate_calls"] for item in items),
                     "usage_calls": sum(item["usage_calls"] for item in items),
                     "output_tokens": sum(item["output_tokens"] for item in items) if complete else None,
                     "candidate_call_seconds": round(seconds, 6)})
    return {"schema_version": 2, "case_count": case_count, "repeats": first["repeats"],
            "source_receipt_sha256": sorted(r["receipt_sha256"] for r in records),
            "engine_sha256": first["engine_sha256"], "config_sha256": first["config_sha256"], "candidates": rows}


def export_usage(runs: list[Path], summary: Path, output: Path) -> dict:
    result = summarize_combined([load_run(run) for run in runs], read_json(summary))
    # Exclusive creation preserves any existing result, even across concurrent exporters.
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, action="append", help="Repeat for each public synthetic run")
    parser.add_argument("--summary", type=Path, required=True, help="Matching export-overall summary")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export_usage(args.run, args.summary, args.out)


if __name__ == "__main__":
    main()
