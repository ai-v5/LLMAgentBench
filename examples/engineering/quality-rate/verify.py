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
    "set": set, "abs": abs, "round": round, "type": lambda value: type(value)}
functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
assert all(isinstance(n, ast.FunctionDef) or (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)) for n in tree.body)
for node in ast.walk(tree):
    assert type(node) in allowed, type(node).__name__
    if isinstance(node, ast.FunctionDef):
        assert not node.decorator_list and not node.name.startswith("__")
    if isinstance(node, ast.Name):
        assert not node.id.startswith("__")
    if isinstance(node, ast.Attribute):
        assert node.attr in {"get", "append", "items", "values", "copy", "pop", "setdefault", "update"}
    if isinstance(node, ast.Call):
        assert (isinstance(node.func, ast.Name) and node.func.id in (set(safe_builtins) | functions)) or isinstance(node.func, ast.Attribute)
namespace = {"__builtins__": safe_builtins}
exec(compile(tree, "candidate.py", "exec"), namespace)
f = namespace["summarize"]
r = f([{"status":"pass","elapsed_s":10}, {"status":"error","elapsed_s":20}, {"status":"timeout","elapsed_s":30}])
assert r["passed"] == 1 and r["elapsed_s"] == 60 and math.isclose(r["passes_per_hour"], 60)
r = f([{"status":"fail","elapsed_s":5}, {"status":"pass","elapsed_s":15}])
assert r["passed"] == 1 and r["elapsed_s"] == 20 and math.isclose(r["passes_per_hour"], 180)
assert f([]) == {"passed":0,"elapsed_s":0,"passes_per_hour":None}
assert f([{"status":"error","elapsed_s":0}])["passes_per_hour"] is None
r = f([{"status":"pass","elapsed_s":10}, {"status":"unscored","elapsed_s":90}])
assert r["passed"] == 1 and r["elapsed_s"] == 100 and math.isclose(r["passes_per_hour"], 36)
