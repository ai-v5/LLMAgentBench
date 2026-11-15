import ast
import builtins
import math
import sys
from pathlib import Path

source = (Path(sys.argv[1]) / 'metrics.py').read_text(encoding='utf-8')
tree = ast.parse(source)
safe_modules = {'math', 'statistics', 'collections', 'itertools', 'functools', 'typing', '__future__'}
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        assert all(alias.name.split('.')[0] in safe_modules for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        assert node.level == 0 and node.module and node.module.split('.')[0] in safe_modules
    if isinstance(node, ast.Name):
        assert not node.id.startswith('__')
    if isinstance(node, ast.Attribute):
        assert not node.attr.startswith('_')

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    assert level == 0 and name.split('.')[0] in safe_modules
    return builtins.__import__(name, globals, locals, fromlist, level)

names = ('abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter', 'float', 'int',
         'isinstance', 'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'range',
         'reversed', 'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
         'Exception', 'TypeError', 'ValueError')
namespace = {'__builtins__': {name: getattr(builtins, name) for name in names}}
namespace['__builtins__']['__import__'] = safe_import
exec(compile(tree, 'metrics.py', 'exec'), namespace)
summarize = namespace['summarize']
groups = [[], [{'status': 'error', 'seconds': 0}],
          [{'status': 'pass', 'seconds': 10}, {'status': 'fail', 'seconds': 20}],
          [{'status': status, 'seconds': seconds} for status, seconds in
           [('pass', 1), ('pass', 2), ('error', 3), ('timeout', 4), ('unscored', 5)]],
          [{'status': 'fail', 'seconds': 3.5}, {'status': 'pass', 'seconds': 0.5}]]
for rows in groups:
    result = summarize(rows)
    passed = sum(row['status'] == 'pass' for row in rows)
    elapsed = sum(row['seconds'] for row in rows)
    assert result['passed'] == passed and result['elapsed_seconds'] == elapsed
    expected = passed * 3600 / elapsed if elapsed else None
    assert result['passes_per_hour'] is None if expected is None else math.isclose(result['passes_per_hour'], expected, rel_tol=1e-9)
