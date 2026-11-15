import json
import math
import sys
from pathlib import Path

value = json.loads((Path(sys.argv[1]) / 'window_report.json').read_text(encoding='utf-8'))
assert type(value['isolated_tokens_per_second']) in (int, float)
assert math.isclose(value['isolated_tokens_per_second'], 1000, abs_tol=1e-6)
assert value['mixed_status'] == 'MIXED'
assert value.get('mixed_tokens_per_second') is None
