"""Inspect the exact staged public candidate without printing matched material."""

from __future__ import annotations

import json
import re
import subprocess
import sys


PATTERNS = {
    "credential_token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,})"),
    "private_key": re.compile(r"^-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----", re.MULTILINE),
    "embedded_url_credentials": re.compile(r"https?://[^\s/:]+:[^\s/@]+@"),
    "private_machine_path": re.compile(r"(?:[A-Za-z]:[\\/]Users[\\/](?!Public\b)[^\s/\\]+|[A-Za-z]:[\\/]WORK[\\/](?:LINGSHU|ai-v5))", re.IGNORECASE),
}


def audit(files: dict[str, bytes]) -> list[dict]:
    findings = []
    for path, raw in files.items():
        if path.startswith(("local/", ".bench-runs/", ".codex/worktrees/")) or path.rsplit("/", 1)[-1].startswith(".env"):
            findings.append({"file": path, "rule": "excluded_path"})
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            findings.append({"file": path, "rule": "binary_requires_explicit_review"})
            continue
        for rule, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append({"file": path, "rule": rule})
        if path.endswith(".json"):
            try:
                value = json.loads(text)
                if isinstance(value, dict) and value.get("visibility") == "private":
                    findings.append({"file": path, "rule": "private_payload"})
            except json.JSONDecodeError:
                findings.append({"file": path, "rule": "invalid_json"})
    return findings


def main() -> int:
    names = subprocess.check_output(["git", "ls-files", "--cached", "-z"]).decode().split("\0")
    files = {name: subprocess.check_output(["git", "show", ":" + name]) for name in names if name}
    findings = audit(files)
    print(json.dumps({"files": len(files), "findings": findings, "boundary": "Pattern scan plus explicit content-scope review; absence of matches is not proof of absence."}))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
