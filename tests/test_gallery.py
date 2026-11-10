import json
import re
from pathlib import Path

import pytest

from llmagentbench.contracts import ContractError
from scripts import export_public_gallery as exporter
from scripts.export_public_gallery import validate_html

ROOT = Path(__file__).resolve().parents[1]


def test_gallery_entries_are_inert_public_drawings():
    data = json.loads((ROOT / "site/gallery.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["entries"]
    for entry in data["entries"]:
        asset = entry.get("html") or entry.get("svg")
        path = ROOT / asset
        assert path.is_file(), asset
        svg = path.read_text(encoding="utf-8")
        low = svg.lower()
        assert "<svg" in low and "</svg>" in low
        assert "animatetransform" in low
        assert "<script" not in low and "foreignobject" not in low
        assert not re.search(r"\son[a-z]+\s*=", svg, re.I)
        assert not re.search(r"(?:src|href)\s*=\s*[\"'](?:https?:)?//", svg, re.I)
        assert entry["label"] and entry["effort"]
        assert entry["id"] == path.stem
        if entry.get("html"):
            validate_html(svg)
    assert {entry["id"] for entry in data["entries"]} >= {"terra-max", "terra-high", "terra-low", "luna-max", "luna-high", "luna-low"}


@pytest.mark.parametrize("unsafe", [
    '<script>alert(1)</script>', '<iframe src="https://example.org"></iframe>',
    '<circle onload="alert(1)"/>', '<use href="https://example.org/x#y"/>',
    '<style>@import "https://example.org/x";</style>',
    '<style>svg { background: image-set("https://example.org/x" 1x); }</style>',
    '<style>svg { background: image-set("/relative" 1x); }</style>',
    '<style/>svg { background: image-set("https://example.org/x" 1x); }</style>',
    '<rect fill="url(https://example.org/x)"/>',
    '<rect style="fill:u&#114;l(/probe)"/>',
    '<filter><feImage href="https://example.org/x"/></filter>',
    '<animate attributeName="href" values="#a;https://example.org"/>',
    '<meta http-equiv="refresh" content="0;url=https://example.org"/>',
])
def test_gallery_html_rejects_active_or_external_content(unsafe):
    with pytest.raises(ContractError):
        validate_html(f"<html><body><svg>{unsafe}</svg></body></html>")


def test_gallery_html_keeps_internal_references():
    validate_html('<html><body><svg><defs><linearGradient id="g"/></defs>'
                  '<rect fill="url(#g)"/><use href="#g"/></svg></body></html>')


@pytest.mark.parametrize("invalid", [None, "private_pack", "private_run", "nonsynthetic_pack", "nonsynthetic_run",
                                     "pack_hash", "case_matrix", "incomplete_receipt", "fixture_call"])
def test_gallery_export_rejects_unverified_or_private_source(monkeypatch, invalid):
    pack = {"manifest": {"visibility": "public", "synthetic": True}, "sha256": "pack-hash",
            "cases": [{"definition": {"id": "crocodile-bike"}}]}
    call = {"evidence_level": "MODEL_RUN", "response": {"files": [
        {"path": "crocodile.html", "content": "<html><body><svg></svg></body></html>"}]}}
    run = {"visibility": "public", "synthetic": True, "pack_sha256": "pack-hash",
           "case_ids": ["crocodile-bike"],
           "candidates": [{"id": "model", "adapter": "codex", "requested_model": "model", "reasoning_effort": "max"}],
           "attempts": [{"candidate_id": "model", "case_id": "crocodile-bike", "repeat": 0,
                         "outcome": "pass", "rounds": [{"call": call}]}]}
    if invalid == "private_pack":
        pack["manifest"]["visibility"] = "private"
    elif invalid == "private_run":
        run["visibility"] = "private"
    elif invalid == "nonsynthetic_pack":
        pack["manifest"]["synthetic"] = False
    elif invalid == "nonsynthetic_run":
        run["synthetic"] = False
    elif invalid == "pack_hash":
        run["pack_sha256"] = "different"
    elif invalid == "case_matrix":
        run["case_ids"] = []
    elif invalid == "fixture_call":
        call["evidence_level"] = "FIXTURE_SMOKE"
    monkeypatch.setattr(exporter, "load_pack", lambda _: pack)
    def load(_):
        if invalid == "incomplete_receipt":
            raise ContractError("Run is incomplete")
        return run
    monkeypatch.setattr(exporter, "load_run", load)
    if invalid is None:
        content, outcome = exporter.selected_drawing(Path("pack"), Path("run"), "model", "max")
        assert content == call["response"]["files"][0]["content"] and outcome == "pass"
    else:
        with pytest.raises(ContractError):
            exporter.selected_drawing(Path("pack"), Path("run"), "model", "max")
