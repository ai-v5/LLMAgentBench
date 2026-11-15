import json
import sys
from pathlib import Path

value = json.loads((Path(sys.argv[1]) / 'diagnosis.json').read_text(encoding='utf-8'))
assert value['status'] == 'CONTAINER_DEVICE_UNAVAILABLE'
assert value['next_check'] == 'CONTAINER_DEVICE_MAPPING'
