"""Result aggregates must satisfy the invariants the results page relies on."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "results/exp-20261111"
MODELS = {"flex": "DSH V4.1 Flash 1017 Flex", "glm": "GLM 5.3"}


def load(folder: Path, name: str) -> dict:
    return json.loads((folder / name).read_text(encoding="utf-8"))


def test_aggregates_match_the_labels_the_site_requests():
    app = (ROOT / "site/app.js").read_text(encoding="utf-8")
    for tag, label in MODELS.items():
        for effort in ("low", "high", "max"):
            folder = EXPERIMENT / tag / effort
            if not folder.is_dir():
                continue
            expected = f"{label} {effort}"
            assert f"`{label} ${{effort}}`" in app or f'"{expected}"' in app, expected
            summary = load(folder, "summary.json")
            overall = load(folder, "overall.json")
            tokens = load(folder, "token-usage.json")
            assert summary["candidates"][0]["label"] == expected
            assert overall["candidates"][0]["label"] == expected
            assert tokens["candidates"][0]["label"] == expected
            assert summary["pack_version"] == overall["pack_version"] == "20261111"
            assert tokens["candidates"][0]["reasoning_effort"] == effort


def test_public_provenance_sources_add_up():
    for tag in MODELS:
        for effort in ("low", "high", "max"):
            folder = EXPERIMENT / tag / effort
            if not folder.is_dir():
                continue
            provenance = load(folder, "provenance.json")
            summary = load(folder, "summary.json")
            sources = provenance["sources"]
            assert all(source["selected_cases"] >= 1 for source in sources), (tag, effort, sources)
            assert sum(source["selected_cases"] for source in sources) == summary["case_count"], (tag, effort)
            assert len({source["receipt_sha256"] for source in sources}) == len(sources), (tag, effort)
            token = load(folder, "token-usage.json")
            assert sorted(token["source_receipt_sha256"]) == sorted(
                source["receipt_sha256"] for source in sources), (tag, effort)
