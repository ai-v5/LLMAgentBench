"""The evaluator owns cases, checks, budgets and result identities."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


class ContractError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=lambda x: (_ for _ in ()).throw(ContractError(f"Non-finite JSON: {x}")))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ContractError("Expected a relative POSIX path")
    parts = PurePosixPath(name).parts
    if PurePosixPath(name).is_absolute() or PureWindowsPath(name).is_absolute() or ".." in parts or ".git" in parts:
        raise ContractError("Path escapes its permitted root")
    root = root.resolve()
    target = root.joinpath(*parts)
    if not target.resolve().is_relative_to(root):
        raise ContractError("Path resolves outside its permitted root")
    cursor = target
    while cursor != root:
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise ContractError("Symlinks and junctions are not supported")
        cursor = cursor.parent
    return target


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value):
        raise ContractError("IDs must be short ASCII identifiers")
    return value


def positive(value: Any, field: str, *, allow_zero: bool = False) -> None:
    try:
        valid = (not isinstance(value, bool) and isinstance(value, (int, float))
                 and math.isfinite(value) and (value >= 0 if allow_zero else value > 0))
    except OverflowError:
        valid = False
    if not valid:
        raise ContractError(f"Invalid {field}")


def validate_case(case: dict, root: Path) -> None:
    identifier(case["id"])
    if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
        raise ContractError("Case requires a prompt")
    if case.get("category") not in {"coding", "analysis", "review", "tool_use"}:
        raise ContractError("Unknown case category")
    for name, content in case.get("inputs", {}).items():
        safe_path(root, name)
        if not isinstance(content, str):
            raise ContractError("Input files must be UTF-8 strings")
    for name in case.get("allowed_write_paths", []):
        safe_path(root, name)
    checks = case.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ContractError("Case must contain evaluator-owned checks")
    seen = set()
    for check in checks:
        check_id = identifier(check["id"])
        if check_id in seen:
            raise ContractError("Duplicate check ID")
        seen.add(check_id)
        kind = check.get("type")
        if kind not in {"json_equal", "number", "python", "llm_rubric"}:
            raise ContractError("Unknown grader type")
        if kind in {"json_equal", "number"}:
            if not isinstance(check.get("path"), list):
                raise ContractError("JSON checks require an explicit path")
            if "expected" not in check:
                raise ContractError("JSON checks require an expected value")
        if kind == "number":
            if type(check["expected"]) not in {int, float}:
                raise ContractError("Expected number must be numeric, not boolean")
            positive(abs(check["expected"]), "expected number", allow_zero=True)
            positive(check.get("atol", 0), "atol", allow_zero=True)
            positive(check.get("rtol", 0), "rtol", allow_zero=True)
        if kind == "python":
            script = safe_path(root, check["script"])
            if not script.is_file():
                raise ContractError("Missing evaluator test script")
        if kind == "llm_rubric" and not check.get("criteria"):
            raise ContractError("LLM grader needs explicit criteria")


def load_pack(path: Path) -> dict:
    path = path.resolve()
    manifest = read_json(path)
    if manifest.get("schema_version") != 1 or manifest.get("visibility") not in {"public", "private"}:
        raise ContractError("Unsupported pack contract")
    identifier(manifest["id"])
    if type(manifest.get("synthetic")) is not bool:
        raise ContractError("Pack must explicitly classify synthetic content")
    if not isinstance(manifest.get("cases"), list) or not manifest["cases"]:
        raise ContractError("Pack cannot be empty")
    cases, seen, files = [], set(), {}
    for relative in manifest["cases"]:
        case_path = safe_path(path.parent, relative)
        case = read_json(case_path)
        validate_case(case, case_path.parent)
        if case["id"] in seen:
            raise ContractError("Duplicate case ID")
        seen.add(case["id"])
        files[relative] = case
        script_hashes = {}
        for check in case["checks"]:
            if check["type"] == "python":
                script = safe_path(case_path.parent, check["script"])
                content = script.read_bytes()
                files[relative + ":" + check["script"]] = content.decode("utf-8")
                script_hashes[check["script"]] = hashlib.sha256(content).hexdigest()
        cases.append({"definition": case, "root": case_path.parent, "script_hashes": script_hashes})
    return {"path": path, "manifest": manifest, "cases": cases, "sha256": digest({"manifest": manifest, "files": files})}


def load_config(path: Path) -> dict:
    config = read_json(path)
    if config.get("schema_version") != 1:
        raise ContractError("Unsupported run configuration")
    for key, default, upper in (("repeats", 1, 20), ("max_repair_rounds", 0, 10)):
        value = config.setdefault(key, default)
        if type(value) is not int or not (0 if key == "max_repair_rounds" else 1) <= value <= upper:
            raise ContractError(f"Invalid {key}")
    positive(config.setdefault("timeout_seconds", 120), "timeout_seconds")
    positive(config.setdefault("check_timeout_seconds", 30), "check_timeout_seconds")
    candidates = config.get("candidates", [])
    if not candidates:
        raise ContractError("No candidates configured")
    seen = set()
    for candidate in candidates:
        candidate_id = identifier(candidate["id"])
        if candidate_id in seen:
            raise ContractError("Duplicate candidate ID")
        seen.add(candidate_id)
        validate_adapter(candidate)
    if config.get("judge"):
        validate_adapter(config["judge"])
    return config


def validate_adapter(adapter: dict) -> None:
    kind = adapter.get("adapter")
    if kind not in {"fixture", "codex", "dsh"}:
        raise ContractError("Unsupported adapter")
    if kind in {"codex", "dsh"} and not adapter.get("model"):
        raise ContractError("Real adapters require an explicit model")
    if kind == "dsh" and not adapter.get("provider"):
        raise ContractError("DSH requires an explicit provider route")
    if kind == "fixture" and not isinstance(adapter.get("responses"), dict):
        raise ContractError("Fixture responses must be explicit")
