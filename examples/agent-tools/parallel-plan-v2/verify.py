import json
import sys
from pathlib import Path

value = json.loads((Path(sys.argv[1]) / 'plan.json').read_text(encoding='utf-8'))
rows = value if isinstance(value, list) else value['rows']
assert isinstance(rows, list) and len(rows) == 2
by_id = {row['id']: row for row in rows}
assert set(by_id) == {'a', 'b'}
for name, nmb, sequences, tokens in [('a', 6, 48, 98304), ('b', 4, 32, 131072)]:
    assert type(by_id[name]['nmb']) is int and by_id[name]['nmb'] == nmb
    assert type(by_id[name]['global_sequences']) is int and by_id[name]['global_sequences'] == sequences
    assert type(by_id[name]['unique_tokens']) is int and by_id[name]['unique_tokens'] == tokens
