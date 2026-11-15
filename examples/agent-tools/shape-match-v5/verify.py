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
        assert all(not alias.name.startswith('_') and alias.name not in {'sys', 'os', 'builtins'}
                   for alias in node.names)
    if isinstance(node, ast.Name):
        assert not node.id.startswith('__')
    if isinstance(node, ast.Attribute):
        assert not node.attr.startswith('_')
        assert node.attr not in {'sys', 'os', 'builtins', 'modules', 'stdin', 'stdout', 'stderr'}

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
outputs = []
for request in payload['requests']:
    expected, observed = request['expected'], request['observed']
    before = copy.deepcopy((expected, observed))
    if request['keyword']:
        value = namespace['matches'](expected=expected, observed=observed)
    else:
        value = namespace['matches'](expected, observed)
    assert type(value) is bool
    outputs.append({'value': value, 'unchanged': (expected, observed) == before})
print('BENCH_SHAPE_RESULT:' + json.dumps(outputs))
'''


def evaluate(requests):
    result = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, sys.argv[1]],
                            input=json.dumps({'requests': requests}),
                            text=True, encoding='utf-8', capture_output=True)
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert lines and lines[-1].startswith('BENCH_SHAPE_RESULT:')
    answers = json.loads(lines[-1].removeprefix('BENCH_SHAPE_RESULT:'))
    assert isinstance(answers, list) and len(answers) == len(requests)
    assert all(isinstance(answer, dict) and answer.get('unchanged') is True
               and type(answer.get('value')) is bool for answer in answers)
    return [answer['value'] for answer in answers]


target = {'op': 'matmul', 'shape': [2, 4], 'dtype': 'bf16', 'device': 'npu'}
checks = [(target, True), ({**target, 'dtype': 'fp32'}, False),
          ({**target, 'device': 'cpu'}, False), ({**target, 'shape': [4, 2]}, False),
          ({**target, 'op': 'attention'}, False), ({'op': 'matmul', 'shape': [2, 4]}, False),
          ({**target, 'extra': 'ignored'}, True)]
requests = [{'expected': target, 'observed': observed, 'keyword': False} for observed, _ in checks]
requests += [{'expected': target, 'observed': target, 'keyword': True},
             {'expected': {'op': 'matmul'}, 'observed': {'op': 'matmul'}, 'keyword': False}]
assert evaluate(requests) == [expected for _, expected in checks] + [True, False]
