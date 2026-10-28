import ast
import math
import sys
from pathlib import Path

tree = ast.parse((Path(sys.argv[1]) / "candidate.py").read_text(encoding="utf-8"))
allowed = {ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign,
    ast.AnnAssign, ast.AugAssign, ast.If, ast.For, ast.Continue, ast.Break, ast.Expr,
    ast.Call, ast.Name, ast.Load, ast.Store, ast.Constant, ast.Dict, ast.List, ast.Tuple,
    ast.Set, ast.Subscript, ast.Slice, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.IfExp, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    ast.Attribute, ast.keyword, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
    ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn}
safe_builtins = {"len": len, "sum": sum, "any": any, "all": all, "enumerate": enumerate,
    "range": range, "sorted": sorted, "min": min, "max": max, "int": int, "float": float,
    "bool": bool, "str": str, "isinstance": isinstance, "list": list, "dict": dict,
    "set": set, "frozenset": frozenset, "tuple": tuple, "bytes": bytes, "bytearray": bytearray,
    "abs": abs, "round": round, "type": lambda value: type(value)}
functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
assert all(isinstance(n, ast.FunctionDef) or (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)) for n in tree.body)
for node in ast.walk(tree):
    assert type(node) in allowed, type(node).__name__
    if isinstance(node, ast.FunctionDef):
        assert not node.decorator_list and not node.name.startswith("__")
    if isinstance(node, ast.Name):
        assert not node.id.startswith("__")
    if isinstance(node, ast.Attribute):
        assert node.attr in {"get", "append", "items", "values", "copy", "pop", "setdefault", "update", "add"}
    if isinstance(node, ast.Call):
        assert (isinstance(node.func, ast.Name) and node.func.id in (set(safe_builtins) | functions)) or isinstance(node.func, ast.Attribute)
namespace = {"__builtins__": safe_builtins}
exec(compile(tree, "candidate.py", "exec"), namespace)
f = namespace["admissible"]
good = {"status":"completed","world_size":2,"offered_concurrency":999,"ranks":[{"rank":0,"native_batch":4,"outputs":[16,16]},{"rank":1,"native_batch":4,"outputs":[16]}]}
assert f(good,4,16) is True
assert f({**good,"ranks":[]},4,16) is False
assert f({**good,"ranks":[good["ranks"][0],good["ranks"][0]]},4,16) is False
assert f({**good,"ranks":[good["ranks"][0],{"rank":1,"native_batch":4,"outputs":[15]}]},4,16) is False
assert f({**good,"ranks":[good["ranks"][0],{"rank":1,"native_batch":4,"outputs":[]}]},4,16) is False
assert f({**good,"ranks":[good["ranks"][0],{"rank":1,"native_batch":5,"outputs":[16]}]},4,16) is False
assert f({**good,"status":"error"},4,16) is False
one = {"status":"completed", "world_size":1, "ranks":[{"rank":0, "native_batch":4, "outputs":[16]}]}
three = {"status":"completed", "world_size":3, "ranks":[{"rank":2, "native_batch":4, "outputs":[16]}, {"rank":0, "native_batch":4, "outputs":[16]}, {"rank":1, "native_batch":4, "outputs":[16]}]}
assert f(one,4,16) is True
assert f(three,4,16) is True
assert f({**one,"world_size":True},4,16) is False
assert f({**one,"world_size":1.0},4,16) is False
assert f({**one,"world_size":0},4,16) is False
