"""Frozen inputs, fresh workspaces, bounded repairs, immutable attempt receipts."""

from __future__ import annotations

import hashlib
import json
import platform
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .adapters import adapter_identity, invoke
from .contracts import (ContractError, canonical, digest, read_json, safe_path,
                        validate_case_families, validate_evaluation_scope, validate_invocation_mode, write_json)
from .graders import grade, outcome


class IdentityDriftError(ContractError):
    """A frozen evaluation identity changed; the run must not resume."""


def workspace_snapshot(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        safe_path(root, relative)
        if path.is_file():
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def archive_workspace(workspace: Path, destination: Path) -> dict:
    """Freeze exactly the bytes observed immediately before grading."""
    files = workspace_snapshot(workspace)
    destination.mkdir()
    for name, expected in files.items():
        content = safe_path(workspace, name).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ContractError("Workspace changed during snapshot")
        target = safe_path(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(content)
    if workspace_snapshot(workspace) != files:
        raise ContractError("Workspace changed during snapshot")
    return files


def engine_digest() -> str:
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))})


def workspace_check(baseline: dict, workspace: Path, allowed: list[str], *, protected_only: bool = False) -> dict:
    current = workspace_snapshot(workspace)
    changed = {name for name in baseline.keys() | current.keys() if baseline.get(name) != current.get(name)}
    if protected_only:
        changed = {name for name in changed if name in baseline}
    return {"id": "workspace_contract", "type": "filesystem", "status": "pass" if changed <= set(allowed) else "fail", "reason": "writes_within_allowlist" if changed <= set(allowed) else "protected_or_unlisted_file_changed"}


def validate_private_output(output: Path) -> None:
    """Reject the public checkout and its common main checkout before writing."""
    engine_checkout = Path(__file__).resolve().parents[1]
    engine_roots = [engine_checkout]
    git_marker = engine_checkout / '.git'
    if git_marker.is_file():
        git_directory = Path(git_marker.read_text().removeprefix('gitdir:').strip())
        if not git_directory.is_absolute():
            git_directory = git_marker.parent / git_directory
        git_directory = git_directory.resolve()
        common_file = git_directory / 'commondir'
        if common_file.is_file():
            engine_roots.append((git_directory / common_file.read_text().strip()).resolve().parent)
    if any(output.resolve().is_relative_to(root) for root in engine_roots):
        raise ContractError('Private results must stay outside the public engine checkout')


def run(pack: dict, config: dict, output: Path) -> dict:
    manifest = pack["manifest"]
    invocation_mode = manifest.get("invocation_mode", "response_patch")
    validate_invocation_mode(invocation_mode)
    if "case_families" in manifest:
        validate_case_families(manifest["case_families"], [entry["definition"]["id"] for entry in pack["cases"]])
    if invocation_mode == "workspace_tools":
        if any(c.get("local_lookup_audit") for c in config["candidates"]):
            raise ContractError("Tool-disabled lookup audit is incompatible with workspace tools")
        if any(c["adapter"] not in {"fixture", "codex", "dsh"} for c in config["candidates"]):
            raise ContractError("Adapter does not support workspace tools")
    output = output.resolve()
    if pack["manifest"]["visibility"] == "private":
        validate_private_output(output)
    if output.exists():
        raise ContractError("Run directory already exists; receipts are never overwritten")
    output.mkdir(parents=True)
    config_fingerprint = digest(config)
    frozen_config = canonical(config)
    config = json.loads(frozen_config)
    record = {
        "schema_version": 1, "run_id": output.name, "created_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": __version__, "engine_sha256": engine_digest(), "python_version": platform.python_version(),
        "platform": platform.system(), "pack_id": manifest["id"], "pack_version": pack.get("version"),
        "pack_sha256": pack["sha256"],
        "visibility": manifest["visibility"], "synthetic": manifest["synthetic"],
        "purpose": manifest.get("purpose", "benchmark"),
        "case_ids": [e["definition"]["id"] for e in pack["cases"]],
        "expected_attempts": len(pack["cases"]) * len(config["candidates"]) * config["repeats"],
        "config_sha256": config_fingerprint, "repeats": config["repeats"],
        "max_repair_rounds": config["max_repair_rounds"], "timeout_seconds": config["timeout_seconds"],
        "check_timeout_seconds": config["check_timeout_seconds"],
        "order_seed": config.get("order_seed", 0), "candidates": [adapter_identity(c, invocation_mode=invocation_mode) if invocation_mode == "workspace_tools" else adapter_identity(c) for c in config["candidates"]],
        "judge": adapter_identity(config["judge"]) if config.get("judge") else None,
        "human_minutes": None, "human_minutes_status": "NOT_MEASURED",
        "metric_boundary": "Automated task outcomes and repair effort are proxies, not measured human labor savings.",
        "state": "running", "attempts": [],
    }
    if "evaluation_scope" in manifest:
        record["evaluation_scope"] = manifest["evaluation_scope"]
    if "invocation_mode" in manifest:
        record["invocation_mode"] = invocation_mode
    if invocation_mode == "workspace_tools":
        record["workspace_snapshot_version"] = 1
    if "case_families" in manifest:
        record["case_families"] = manifest["case_families"]
    write_json(output / "manifest.json", record)
    def verify_frozen_identity() -> None:
        if record["state"] == "invalidated":
            raise IdentityDriftError("Evaluation has already been invalidated")
        try:
            changed = (engine_digest() != record["engine_sha256"]
                       or [adapter_identity(c, invocation_mode=invocation_mode) if invocation_mode == "workspace_tools" else adapter_identity(c) for c in config["candidates"]] != record["candidates"]
                       or (adapter_identity(config["judge"]) if config.get("judge") else None) != record["judge"])
        except (OSError, ValueError, TypeError, KeyError):
            changed = True
        if changed:
            record["state"] = "invalidated"
            record["invalid_reason"] = "engine_or_adapter_identity_changed"
            write_json(output / "manifest.json", record)
            raise IdentityDriftError("Engine or adapter identity changed during evaluation")
    def capture_workspace(workspace: Path, round_root: Path) -> dict:
        try:
            return archive_workspace(workspace, round_root / "workspace_snapshot")
        except (OSError, ContractError):
            record["state"] = "invalidated"
            record["invalid_reason"] = "workspace_snapshot_unavailable"
            write_json(output / "manifest.json", record)
            raise IdentityDriftError("Workspace snapshot unavailable")
    jobs = [(entry, candidate, repeat) for entry in pack["cases"] for repeat in range(config["repeats"]) for candidate in config["candidates"]]
    random.Random(config.get("order_seed", 0)).shuffle(jobs)
    for index, (entry, candidate, repeat) in enumerate(jobs):
        verify_frozen_identity()
        case = entry["definition"]
        attempt_id = f"{index:04d}-{candidate['id']}-{case['id']}-r{repeat}"
        attempt_root = output / "attempts" / attempt_id
        workspace = attempt_root / "workspace"
        workspace.mkdir(parents=True)
        for name, text in case.get("inputs", {}).items():
            target = safe_path(workspace, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        baseline = workspace_snapshot(workspace)
        attempt = {"id": attempt_id, "candidate_id": candidate["id"], "case_id": case["id"], "category": case["category"], "repeat": repeat,
                   "rounds": [], "outcome": "error", "first_pass": False, "repair_rounds": 0}
        if "case_families" in manifest:
            attempt["family"] = manifest["case_families"][case["id"]]
        previous = None
        started = time.monotonic()
        for round_number in range(config["max_repair_rounds"] + 1):
            verify_frozen_identity()
            round_root = attempt_root / f"round-{round_number}"
            round_root.mkdir()
            payload = {"case_id": case["id"], "task": case["prompt"],
                       "allowed_write_paths": case.get("allowed_write_paths", []), "round": round_number}
            if invocation_mode == "workspace_tools":
                payload["input_paths"] = list(case.get("inputs", {}))
            else:
                payload["inputs"] = case.get("inputs", {})
            if previous:
                payload["previous_response"] = previous["response"]
                payload["feedback"] = [{"id": c["id"], "status": c["status"]} for c in previous["checks"]]
            call = (invoke(candidate, payload, workspace, round_root / "adapter", config["timeout_seconds"], invocation_mode=invocation_mode)
                    if invocation_mode == "workspace_tools" else
                    invoke(candidate, payload, workspace, round_root / "adapter", config["timeout_seconds"]))
            verify_frozen_identity()
            checks, judge_calls = [], []
            workspace_files = None
            state = call["status"]
            if state == "format_error":
                checks = [{"id": "response_contract", "type": "response", "status": "fail",
                           "reason": "invalid_response_format"}]
                state = outcome(checks)
            elif state == "ok":
                try:
                    for change in call["response"]["files"]:
                        if change["path"] not in case.get("allowed_write_paths", []):
                            raise ContractError("Unlisted output file")
                        target = safe_path(workspace, change["path"])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(change["content"].encode("utf-8"))
                    if invocation_mode == "workspace_tools":
                        workspace_files = capture_workspace(workspace, round_root)
                    check = workspace_check(baseline, workspace, case.get("allowed_write_paths", []), protected_only=invocation_mode == "workspace_tools")
                    checks = [check]
                    if check["status"] == "pass":
                        graded, judge_calls = grade(case, entry["root"], call["response"], workspace, round_root, config,
                                                    script_hashes=entry["script_hashes"])
                        verify_frozen_identity()
                        if invocation_mode == "workspace_tools" and workspace_snapshot(workspace) != workspace_files:
                            checks = [{"id": "workspace_contract", "type": "filesystem", "status": "unknown", "reason": "grader_changed_workspace"}]
                        else:
                            checks.extend(graded)
                            checks[0] = workspace_check(baseline, workspace, case.get("allowed_write_paths", []), protected_only=invocation_mode == "workspace_tools")
                    state = outcome(checks)
                except IdentityDriftError:
                    raise
                except (ContractError, OSError):
                    checks = [{"id": "workspace_contract", "type": "filesystem", "status": "fail", "reason": "invalid_output_path_or_workspace"}]
                    state = "fail"
            if invocation_mode == "workspace_tools" and workspace_files is None:
                workspace_files = capture_workspace(workspace, round_root)
            previous = {"response": call["response"], "checks": checks}
            round_record = {"round": round_number, "outcome": state, "call": call, "checks": checks, "judge_calls": judge_calls}
            if invocation_mode == "workspace_tools":
                round_record["workspace_files"] = workspace_files
            round_record["receipt_sha256"] = digest(round_record)
            write_json(round_root / "receipt.json", round_record)
            attempt["rounds"].append(round_record)
            attempt["outcome"] = state
            attempt["repair_rounds"] = round_number
            if round_number == 0:
                attempt["first_pass"] = state == "pass"
            if state != "fail":
                break
            if any(c["id"] == "workspace_contract" and c["status"] == "fail" for c in checks):
                break
        attempt["elapsed_seconds"] = round(time.monotonic() - started, 6)
        attempt["receipt_sha256"] = digest(attempt)
        write_json(attempt_root / "receipt.json", attempt)
        record["attempts"].append(attempt)
        write_json(output / "manifest.json", record)
    verify_frozen_identity()
    record["state"] = "completed"
    record["receipt_sha256"] = digest(record)
    write_json(output / "manifest.json", record)
    return record


def load_run(root: Path) -> dict:
    """Detect missing or modified receipts before reporting or exporting."""
    from collections import Counter
    record = read_json(root / "manifest.json")
    if record["state"] != "completed":
        raise ContractError("Run is incomplete")
    if "evaluation_scope" in record:
        validate_evaluation_scope(record["evaluation_scope"])
    if "invocation_mode" in record:
        validate_invocation_mode(record["invocation_mode"])
    if "workspace_snapshot_version" in record and record["workspace_snapshot_version"] != 1:
        raise ContractError("Unknown workspace snapshot version")
    if "case_families" in record:
        validate_case_families(record["case_families"], record["case_ids"])
        if any(a.get("family") != record["case_families"].get(a["case_id"]) for a in record["attempts"]):
            raise ContractError("Attempt case family differs from run")
    expected = Counter((c["id"], case_id, repeat) for c in record["candidates"] for case_id in record["case_ids"] for repeat in range(record["repeats"]))
    actual = Counter((a["candidate_id"], a["case_id"], a["repeat"]) for a in record["attempts"])
    if expected != actual or len(record["attempts"]) != record["expected_attempts"]:
        raise ContractError("Assigned attempts are missing or duplicated")
    def verify(value: dict) -> None:
        if value.get("receipt_sha256") != digest({k: v for k, v in value.items() if k != "receipt_sha256"}):
            raise ContractError("Receipt fingerprint mismatch")
    verify(record)
    for attempt in record["attempts"]:
        verify(attempt)
        directory = safe_path(root / "attempts", attempt["id"])
        if read_json(directory / "receipt.json") != attempt:
            raise ContractError("Attempt receipt differs from run manifest")
        for item in attempt["rounds"]:
            verify(item)
            if read_json(directory / f"round-{item['round']}" / "receipt.json") != item:
                raise ContractError("Round receipt differs from attempt")
            if record.get("workspace_snapshot_version") == 1:
                snapshot = directory / f"round-{item['round']}" / "workspace_snapshot"
                try:
                    if not snapshot.is_dir() or workspace_snapshot(snapshot) != item.get("workspace_files"):
                        raise ContractError("Workspace snapshot differs from receipt")
                except OSError as error:
                    raise ContractError("Workspace snapshot unavailable") from error
    return record
