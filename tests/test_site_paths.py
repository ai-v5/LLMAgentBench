"""Every result path referenced by site/app.js must exist in the checkout."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_site_batches_reference_existing_files():
    app = (ROOT / "site/app.js").read_text(encoding="utf-8")
    missing = []
    checked = 0
    for match in re.finditer(r"results/[A-Za-z0-9_\-./]*\.json", app):
        path = match.group(0)
        if "${effort}" in path:
            for effort in ("low", "high", "max"):
                candidate = ROOT / path.replace("${effort}", effort)
                checked += 1
                if not candidate.is_file():
                    missing.append(str(candidate.relative_to(ROOT)))
            continue
        candidate = ROOT / path
        checked += 1
        if not candidate.is_file():
            missing.append(path)
    assert checked, "site/app.js must reference result files"
    assert not missing, f"missing result files: {sorted(set(missing))}"


def test_index_links_resolve():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    missing = [href for href in re.findall(r'href="(results/[^"]+)"', html) if not (ROOT / href).is_file()]
    assert not missing, f"broken result links: {missing}"


def test_gallery_entries_reference_existing_artifacts():
    import json

    gallery = json.loads((ROOT / "site/gallery.json").read_text(encoding="utf-8"))
    missing = [entry["html"] for entry in gallery["entries"] if not (ROOT / entry["html"]).is_file()]
    assert not missing, f"missing gallery artifacts: {missing}"
