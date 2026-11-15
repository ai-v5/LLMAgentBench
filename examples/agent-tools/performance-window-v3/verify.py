import json
import math
import sys
from pathlib import Path

value = json.loads((Path(sys.argv[1]) / 'window_report.json').read_text(encoding='utf-8'))
if isinstance(value, dict):
    for key in ('mixed_tokens_per_second', 'mixed_decode_tokens_per_second'):
        assert value.get(key) is None
if isinstance(value, list) or (isinstance(value, dict) and isinstance(value.get('windows'), list)):
    rows = value if isinstance(value, list) else value['windows']
    assert len(rows) == 2
    by_id = {row['id']: row for row in rows}
    assert set(by_id) == {'isolated', 'mixed'}
    isolated = by_id['isolated'].get('isolated_tokens_per_second')
    mixed = by_id['mixed']
    assert mixed.get('mixed_status') == 'MIXED'
    for key in ('mixed_tokens_per_second', 'mixed_decode_tokens_per_second', 'tokens_per_second',
                'decode_tokens_per_second', 'isolated_tokens_per_second'):
        assert mixed.get(key) is None
else:
    isolated = value['isolated_tokens_per_second']
    assert value['mixed_status'] == 'MIXED'
    assert value.get('mixed_tokens_per_second') is None
assert type(isolated) in (int, float)
assert math.isclose(isolated, 1000, abs_tol=1e-6)
if isinstance(value, dict):
    for key in ('tokens_per_second', 'decode_tokens_per_second'):
        extra = value.get(key)
        if extra is not None:
            assert type(extra) in (int, float) and math.isclose(extra, isolated, abs_tol=1e-6)
