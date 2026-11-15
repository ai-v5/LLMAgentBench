import json
import math
import sys
from pathlib import Path

value = json.loads((Path(sys.argv[1]) / 'decision.json').read_text(encoding='utf-8'))
assert isinstance(value['eligible'], list) and len(value['eligible']) == 2
assert set(value['eligible']) == {'m1', 'm6'}
assert isinstance(value['missing'], list) and value['missing'] == ['m5']
assert type(value['mean_ms']) in (int, float) and math.isclose(value['mean_ms'], 3.0, abs_tol=1e-6)
