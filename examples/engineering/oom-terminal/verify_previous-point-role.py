import json, sys
from pathlib import Path
data = json.loads((Path(sys.argv[1]) / 'answer.json').read_text(encoding='utf-8'))
value = data
for key in ["previous_point_role"]:
    value = value[key]
expected = json.loads("\"OTHER_SHAPE_MEASURED\"")
assert json.dumps(value, ensure_ascii=False, sort_keys=True) == json.dumps(expected, ensure_ascii=False, sort_keys=True)
