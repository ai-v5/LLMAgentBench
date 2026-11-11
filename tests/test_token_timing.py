"""Token aggregates must expose the timing the displayed rate was divided by."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "results/exp-20261111"


def test_token_aggregates_declare_usage_timing():
    for tag in ("flex", "glm"):
        for effort in ("low", "high", "max"):
            folder = EXPERIMENT / tag / effort
            if not folder.is_dir():
                continue
            tokens = json.loads((folder / "token-usage.json").read_text(encoding="utf-8"))
            row = tokens["candidates"][0]
            if row["output_tokens"] is None:
                continue
            assert row["usage_calls"] >= 1, (tag, effort)
            assert row["usage_calls"] <= row["candidate_calls"], (tag, effort)
            seconds = row.get("usage_call_seconds")
            assert isinstance(seconds, (int, float)) and seconds > 0, (tag, effort)
            assert seconds <= row["candidate_call_seconds"] + 0.01, (tag, effort)
            if row["usage_calls"] == row["candidate_calls"]:
                assert abs(seconds - row["candidate_call_seconds"]) <= 0.01, (tag, effort)
