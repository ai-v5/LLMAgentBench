import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gallery_entries_are_inert_svg():
    data = json.loads((ROOT / "site/gallery.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["entries"]
    for entry in data["entries"]:
        path = ROOT / entry["svg"]
        assert path.is_file(), entry["svg"]
        svg = path.read_text(encoding="utf-8")
        low = svg.lower()
        assert "<svg" in low and "</svg>" in low
        assert "animatetransform" in low
        assert "<script" not in low and "foreignobject" not in low
        assert not re.search(r"\son[a-z]+\s*=", svg, re.I)
        assert not re.search(r"(?:src|href)\s*=\s*[\"'](?:https?:)?//", svg, re.I)
        assert entry["label"] and entry["effort"]
        assert entry["id"] == path.stem
