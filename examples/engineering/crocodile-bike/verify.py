import re
import sys
from pathlib import Path

path = Path(sys.argv[1]) / "crocodile.html"
assert path.is_file(), "missing crocodile.html"
html = path.read_text(encoding="utf-8")
low = html.lower()
assert "<html" in low and "</html>" in low and "<body" in low
assert "<svg" in low and "</svg>" in low
assert "<script" not in low
clean = low.replace("http://www.w3.org/", "").replace("https://www.w3.org/", "")
assert "http://" not in clean and "https://" not in clean
assert len(re.findall(r"<circle\b", low)) >= 2
assert len(re.findall(r"<path\b", low)) >= 3
rotations = re.findall(r"<animatetransform\b[^>]*type\s*=\s*[\"']rotate[\"']", low)
assert len(rotations) >= 2, "wheels need animateTransform rotate"
animates = re.findall(r"<animate\b", low)
motions = re.findall(r"<animatetransform\b[^>]*type\s*=\s*[\"'](?:translate|scale)[\"']", low)
assert len(animates) + len(motions) >= 1, "legs/body need an animation"
assert "crocodile" in low or "croc" in low or "鳄鱼" in html
