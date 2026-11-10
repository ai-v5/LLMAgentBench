import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gallery_entries_are_inert_svg_html():
    data = json.loads((ROOT / "site/gallery.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["entries"]
    for entry in data["entries"]:
        path = ROOT / entry["file"]
        assert path.is_file(), entry["file"]
        text = path.read_text(encoding="utf-8")
        low = text.lower()
        assert "<html" in low and "<svg" in low
        assert "animatetransform" in low
        assert "<script" not in low
        assert not re.search(r"(?:src|href)\s*=\s*[\"'](?:https?:)?//", text, re.I)
        assert entry["label"] and entry["effort"]
        assert entry["id"] == path.stem
