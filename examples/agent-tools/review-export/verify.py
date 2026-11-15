import json
import sys
from pathlib import Path

value = json.loads((Path(sys.argv[1]) / 'review.json').read_text(encoding='utf-8'))
issues = value['issues']
assert isinstance(issues, list) and len(issues) == 2
assert set(issues) == {'missing_assignment_denominator', 'private_case_details_exported'}
