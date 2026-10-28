"""Aggregate every assigned attempt, including errors, timeouts and unscored cases."""

from __future__ import annotations

import statistics
import re
from pathlib import Path

from .contracts import ContractError, digest, write_json


def summarize(record: dict) -> dict:
    rows = []
    for candidate in record["candidates"]:
        attempts = [a for a in record["attempts"] if a["candidate_id"] == candidate["id"]]
        if not attempts:
            continue
        calls = [call for a in attempts for r in a["rounds"] for call in [r["call"], *r["judge_calls"]]]
        evidence = "FIXTURE_SMOKE" if any(c["evidence_level"] == "FIXTURE_SMOKE" for c in calls) else "MODEL_RUN"
        counts = {state: sum(a["outcome"] == state for a in attempts) for state in ("pass", "fail", "unscored", "error", "timeout")}
        attempt_seconds = sum(a["elapsed_seconds"] for a in attempts)
        candidate_seconds = sum(r["call"]["elapsed_seconds"] for a in attempts for r in a["rounds"])
        judge_seconds = sum(c["elapsed_seconds"] for a in attempts for r in a["rounds"] for c in r["judge_calls"])
        def stats(group):
            return {"assigned": len(group), "passed": sum(a["outcome"] == "pass" for a in group),
                    "first_passed": sum(a["first_pass"] for a in group)}
        rows.append({
            "candidate_id": candidate["id"], "adapter": candidate["adapter"],
            "requested_model": candidate["requested_model"], "reasoning_effort": candidate["reasoning_effort"],
            "candidate_sha256": candidate["config_sha256"], "evidence_level": evidence,
            "assigned": len(attempts), "outcomes": counts,
            "first_pass_rate": sum(a["first_pass"] for a in attempts) / len(attempts),
            "strict_success_rate": counts["pass"] / len(attempts),
            "mean_repair_rounds": statistics.mean(a["repair_rounds"] for a in attempts),
            "mean_elapsed_seconds": statistics.mean(a["elapsed_seconds"] for a in attempts),
            "max_elapsed_seconds": max(a["elapsed_seconds"] for a in attempts),
            "evaluated_attempt_seconds": attempt_seconds,
            "candidate_call_seconds": candidate_seconds,
            "judge_call_seconds": judge_seconds,
            "effective_passes_per_hour": counts["pass"] * 3600 / attempt_seconds if attempt_seconds > 0 else None,
            "adapter_invocations": len(calls),
            "usage_complete": all(c.get("usage") is not None for c in calls),
            "total_cost_usd": sum(c["cost_usd"] for c in calls) if all(c.get("cost_usd") is not None for c in calls) else None,
            "human_minutes": None, "human_minutes_status": "NOT_MEASURED",
            "by_category": {category: stats([a for a in attempts if a["category"] == category]) for category in sorted({a["category"] for a in attempts})},
        })
    return {
        "schema_version": 1, "run_id": record["run_id"], "state": record["state"],
        "visibility": record["visibility"], "synthetic": record["synthetic"],
        "purpose": record.get("purpose", "benchmark"),
        "source_receipt_sha256": record.get("receipt_sha256"),
        "pack_id": record["pack_id"], "pack_sha256": record["pack_sha256"],
        "engine_version": record["engine_version"], "engine_sha256": record["engine_sha256"],
        "config_sha256": record["config_sha256"], "repeats": record["repeats"],
        "max_repair_rounds": record["max_repair_rounds"], "timeout_seconds": record["timeout_seconds"],
        "check_timeout_seconds": record["check_timeout_seconds"],
        "metric_boundary": record["metric_boundary"], "candidates": rows,
    }


def markdown(summary: dict) -> str:
    data_scope = "合成输入" if summary["synthetic"] else "非合成输入"
    lines = ["# 评估结果", "", f"Run: `{summary['run_id']}` · state: `{summary['state']}`", "",
             f"数据：{data_scope}；用途：`{summary['purpose']}`；可见性：`{summary['visibility']}`。", "",
             "自动验收与修复指标；人工核验时间未测量。小样本不能作为模型排名。", "",
             "| 候选 | 证据 | 样本 | 首次通过率 | 预算内通过率 | 失败/未知/错误/超时 | 平均耗时(s) | 候选调用总耗时(s) | 有效吞吐(通过题/小时) |",
             "|---|---|---:|---:|---:|---|---:|---:|---:|"]
    for row in summary["candidates"]:
        outcomes = row["outcomes"]
        throughput = f"{row['effective_passes_per_hour']:.2f}" if row['effective_passes_per_hour'] is not None else "未知"
        lines.append(f"| {row['candidate_id']} | {row['evidence_level']} | {row['assigned']} | {row['first_pass_rate']:.1%} | {row['strict_success_rate']:.1%} | {outcomes['fail']}/{outcomes['unscored']}/{outcomes['error']}/{outcomes['timeout']} | {row['mean_elapsed_seconds']:.3f} | {row['candidate_call_seconds']:.3f} | {throughput} |")
    lines += ["", f"Pack SHA256: `{summary['pack_sha256']}`", "", f"Engine SHA256: `{summary['engine_sha256']}`", "",
              "成本未知时为 null；费用不由模型猜测。通过率包含全部分配样本；修复轮次不是独立样本。", "",
              "有效吞吐 = 预算内通过数 / 全部尝试计时之和 × 3600。尝试计时从输入准备完成后开始，包含候选调用、CLI 内的网络与服务端排队等待、自动检查、LLM 评分器调用、修复和轮次收据写入；不含输入准备、样本开始前的评估器等待、最终样本收据写入或人工核验。此值是本次串行评估的指标，不是并发服务吞吐。", "",
              "候选模型为请求值；服务端实际模型身份未观测时不能独立确认。", ""]
    return "\n".join(lines)


def export_public(record: dict, output: Path) -> dict:
    if record["state"] != "completed":
        raise ContractError("Cannot export an incomplete run")
    if record["visibility"] != "public" or record["synthetic"] is not True:
        raise ContractError("Private or non-synthetic runs cannot be exported by this command")
    if output.exists():
        raise ContractError("Export destination already exists")
    summary = summarize(record)
    summary["export_sha256"] = digest(summary)
    output.mkdir(parents=True)
    write_json(output / "summary.json", summary)
    (output / "report.md").write_text(markdown(summary), encoding="utf-8")
    return summary


def export_overall(run_paths: list[Path], output: Path, labels: dict[str, str], *, allow_private: bool = False) -> dict:
    """Publish only explicitly labelled overall counts/timings from verified runs."""
    from .runner import load_run

    if not run_paths or output.exists():
        raise ContractError("Overall export requires runs and a new destination")
    records = [load_run(path) for path in run_paths]
    if any(r["visibility"] == "private" or not r["synthetic"] for r in records) and not allow_private:
        raise ContractError("Private overall totals require explicit authorization")
    if len({r["receipt_sha256"] for r in records}) != len(records) or len({r["pack_sha256"] for r in records}) != len(records):
        raise ContractError("Duplicate runs or packs cannot be counted twice")
    if len({r["engine_sha256"] for r in records}) != 1 or len({r["config_sha256"] for r in records}) != 1:
        raise ContractError("Engine and evaluation configuration must match")
    candidates = records[0]["candidates"]
    if any(r["candidates"] != candidates or r["judge"] != records[0]["judge"] for r in records):
        raise ContractError("Frozen candidate or judge identity differs between runs")
    if not isinstance(labels, dict) or set(labels) != {c["id"] for c in candidates} or len(set(labels.values())) != len(labels):
        raise ContractError("Provide one distinct public label for every candidate")
    if any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 +._-]{0,79}", v) for v in labels.values()):
        raise ContractError("Invalid public label")
    rows = []
    for candidate in candidates:
        attempts = [a for r in records for a in r["attempts"] if a["candidate_id"] == candidate["id"]]
        counts = {s: sum(a["outcome"] == s for a in attempts) for s in ("pass", "fail", "unscored", "error", "timeout")}
        elapsed = sum(a["elapsed_seconds"] for a in attempts)
        passed_elapsed = [a["elapsed_seconds"] for a in attempts if a["outcome"] == "pass"]
        calls = [c for a in attempts for rnd in a["rounds"] for c in [rnd["call"], *rnd["judge_calls"]]]
        rows.append({
            "label": labels[candidate["id"]],
            "evidence": "FIXTURE_SMOKE" if any(c["evidence_level"] == "FIXTURE_SMOKE" for c in calls) else "MODEL_RUN",
            "assigned": len(attempts), "first_passed": sum(bool(a["first_pass"]) for a in attempts),
            "passed": counts["pass"], "failed": counts["fail"], "unscored": counts["unscored"],
            "errors": counts["error"], "timeouts": counts["timeout"],
            "attempt_seconds": elapsed, "candidate_call_seconds": sum(rnd["call"]["elapsed_seconds"] for a in attempts for rnd in a["rounds"]),
            "judge_call_seconds": sum(c["elapsed_seconds"] for a in attempts for rnd in a["rounds"] for c in rnd["judge_calls"]),
            "mean_attempt_seconds": elapsed / len(attempts),
            "mean_pass_seconds": statistics.mean(passed_elapsed) if passed_elapsed else None,
            "effective_passes_per_hour": counts["pass"] * 3600 / elapsed if elapsed > 0 else None,
        })
    result = {"schema_version": 1, "case_count": sum(len(r["case_ids"]) for r in records),
              "repeats": records[0]["repeats"], "candidates": rows}
    lines = ["# 总体评估汇总", "", "仅发布总体数量与耗时；通过率和吞吐不代表人工核验时间。", "",
             f"总题数：{result['case_count']}；每题重复：{result['repeats']}。", "",
             "| 候选 | 首次通过 | 预算内通过 | 失败/未评分/错误/超时 | 平均尝试耗时(s) | 有效吞吐(题/小时) |",
             "|---|---:|---:|---|---:|---:|"]
    for row in rows:
        speed = f"{row['effective_passes_per_hour']:.2f}" if row['effective_passes_per_hour'] is not None else "未知"
        lines.append(f"| {row['label']} | {row['first_passed']}/{row['assigned']} | {row['passed']}/{row['assigned']} | {row['failed']}/{row['unscored']}/{row['errors']}/{row['timeouts']} | {row['mean_attempt_seconds']:.2f} | {speed} |")
    lines += ["", "有效吞吐为预算内通过数除以全部尝试计时，包含调用、自动检查、LLM 评分与修复；不是并发服务吞吐。", ""]
    output.mkdir(parents=True)
    write_json(output / "summary.json", result)
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return result
