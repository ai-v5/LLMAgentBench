import json
import math
import sys
from pathlib import Path

value = json.loads((Path(sys.argv[1]) / 'summary.json').read_text(encoding='utf-8'))
expected = {'assigned': 6, 'passed': 1, 'failed': 1, 'errors': 1,
            'timeouts': 1, 'unscored': 1, 'missing': 1, 'elapsed_seconds': 100}
for key, wanted in expected.items():
    assert type(value[key]) in (int, float) and value[key] == wanted
assert type(value['passes_per_hour']) in (int, float)
assert math.isclose(value['passes_per_hour'], 36.0, rel_tol=0, abs_tol=1e-6)
