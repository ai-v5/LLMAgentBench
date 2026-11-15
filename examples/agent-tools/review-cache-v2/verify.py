import json
import sys
from pathlib import Path

value = json.loads((Path(sys.argv[1]) / 'review.json').read_text(encoding='utf-8'))
issues = value['issues']
assert isinstance(issues, list) and len(issues) == 2
ids = [item if isinstance(item, str) else item.get('code', item.get('id')) if isinstance(item, dict) else None for item in issues]
assert set(ids) == {'CACHE_IDENTITY_INCOMPLETE', 'MISSING_TREATED_AS_ZERO'}
