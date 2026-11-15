import ast
import builtins
import copy
import sys
from pathlib import Path

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
    if isinstance(value, type) and issubclass(value, BaseException)})
namespace['__builtins__'].update({name: getattr(builtins, name) for name in
    ('NotImplemented', 'Ellipsis', 'complex', 'hash', 'ord', 'chr', 'repr', 'format',
     'pow', 'divmod', 'bin', 'oct', 'hex', 'ascii', 'callable')})
namespace['__builtins__']['__import__'] = safe_import
exec(compile(tree, 'shape_match.py', 'exec'), namespace)
matches = namespace['matches']
target = {'op': 'matmul', 'shape': [2, 4], 'dtype': 'bf16', 'device': 'npu'}
checks = [(target, True), ({**target, 'dtype': 'fp32'}, False),
          ({**target, 'device': 'cpu'}, False), ({**target, 'shape': [4, 2]}, False),
          ({**target, 'op': 'attention'}, False), ({'op': 'matmul', 'shape': [2, 4]}, False),
          ({**target, 'extra': 'ignored'}, True)]
for observed, expected in checks:
    before_target, before_observed = copy.deepcopy(target), copy.deepcopy(observed)
    assert matches(target, observed) is expected
    assert target == before_target and observed == before_observed
assert matches({'op': 'matmul'}, {'op': 'matmul'}) is False
