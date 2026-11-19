import json, math, sys
from pathlib import Path
data = json.loads((Path(sys.argv[1]) / 'answer.json').read_text(encoding='utf-8'))
value = data
for key in ["compute_seconds"]:
    value = value[key]
assert type(value) in (int, float), type(value)
assert math.isclose(value, 0.01, rel_tol=0, abs_tol=1e-10)
