import json, sys
from pathlib import Path
data = json.loads((Path(sys.argv[1]) / 'answer.json').read_text(encoding='utf-8'))
value = data
for key in ["terminal_state"]:
    value = value[key]
expected = json.loads("\"OOM\"")
assert json.dumps(value, ensure_ascii=False, sort_keys=True) == json.dumps(expected, ensure_ascii=False, sort_keys=True)
