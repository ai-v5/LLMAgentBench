import json, math, sys
from pathlib import Path
data = json.loads((Path(sys.argv[1]) / 'answer.json').read_text(encoding='utf-8'))
value = data
for key in ["decode_tokens_per_s"]:
    value = value[key]
assert type(value) in (int, float), type(value)
assert math.isclose(value, 533.3333333333334, rel_tol=0, abs_tol=0.01)
