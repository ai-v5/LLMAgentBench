import json
import subprocess
import sys
from pathlib import Path


# Candidate code runs in a child so it cannot alter the parent's test list.
# This is not an operating-system sandbox for untrusted code.
CHILD = r'''
import ast
import builtins
import copy
import json
import sys
from pathlib import Path

payload = json.loads(sys.stdin.read())
tree = ast.parse((Path(sys.argv[1]) / 'shape_match.py').read_text(encoding='utf-8'))
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
         'Exception', 'TypeError', 'ValueError', 'KeyError', 'object', 'frozenset', 'bytes', 'bytearray', 'slice')
namespace = {'__builtins__': {name: getattr(builtins, name) for name in names}}
namespace['__builtins__'].update({name: value for name, value in vars(builtins).items()
    if isinstance(value, type) and issubclass(value, Exception)})
namespace['__builtins__'].update({name: getattr(builtins, name) for name in
    ('NotImplemented', 'Ellipsis', 'complex', 'hash', 'ord', 'chr', 'repr', 'format',
     'pow', 'divmod', 'bin', 'oct', 'hex', 'ascii', 'callable')})
namespace['__builtins__']['__import__'] = safe_import
exec(compile(tree, 'shape_match.py', 'exec'), namespace)
expected, observed = payload['expected'], payload['observed']
before = copy.deepcopy((expected, observed))
if payload['keyword']:
    value = namespace['matches'](expected=expected, observed=observed)
else:
    value = namespace['matches'](expected, observed)
assert type(value) is bool
print('BENCH_SHAPE_RESULT:' + json.dumps({'value': value, 'unchanged': (expected, observed) == before}))
'''


def matches(expected, observed, *, keyword=False):
    result = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, sys.argv[1]],
                            input=json.dumps({'expected': expected, 'observed': observed, 'keyword': keyword}),
                            text=True, encoding='utf-8', capture_output=True)
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert lines and lines[-1].startswith('BENCH_SHAPE_RESULT:')
    answer = json.loads(lines[-1].removeprefix('BENCH_SHAPE_RESULT:'))
    assert answer.get('unchanged') is True and type(answer.get('value')) is bool
    return answer['value']


target = {'op': 'matmul', 'shape': [2, 4], 'dtype': 'bf16', 'device': 'npu'}
checks = [(target, True), ({**target, 'dtype': 'fp32'}, False),
          ({**target, 'device': 'cpu'}, False), ({**target, 'shape': [4, 2]}, False),
          ({**target, 'op': 'attention'}, False), ({'op': 'matmul', 'shape': [2, 4]}, False),
          ({**target, 'extra': 'ignored'}, True)]
for observed, expected in checks:
    assert matches(target, observed) is expected
assert matches(target, target, keyword=True) is True
assert matches({'op': 'matmul'}, {'op': 'matmul'}) is False
