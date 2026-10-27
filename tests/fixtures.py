"""Synthetic adapter answers; these are evaluator tests, never model measurements."""


GOOD = {
    "roofline": {"answer": {"compute_seconds": 0.01, "memory_seconds": 0.04, "lower_bound_seconds": 0.04, "evidence": "ANALYTICAL_ESTIMATE"}},
    "unknown": {"answer": {"target_latency_ms": None, "status": "UNKNOWN"}},
    "patch": {"answer": "fixed", "files": [{"path": "calc.py", "content": "def per_item_us(total_us, count):\n    if count is None or count <= 0:\n        return None\n    return total_us / count\n"}]},
    "explanation": {"answer": {"conclusion": "已知发生 OOM 且没有计时样本；性能未知，不作为有效测量；未获授权不重试。", "evidence_status": "UNAVAILABLE", "latency_ms": None}},
}
BAD = {
    "roofline": {"answer": {"compute_seconds": 0.01, "memory_seconds": 0.04, "lower_bound_seconds": 0.01, "evidence": "MEASURED"}},
    "unknown": {"answer": {"target_latency_ms": 0, "status": "MEASURED"}},
    "patch": {"answer": "done", "files": []},
    "explanation": {"answer": {"conclusion": "Retry it.", "evidence_status": "MEASURED", "latency_ms": 0}},
}
JUDGE = {"adapter": "fixture", "responses": {"explanation.rubric": {"answer": {"verdict": True, "reason": "合成夹具符合给定 rubric。", "evidence": [{"source": "answer", "quote": "OOM"}]}}}}


def demo_config():
    return {
        "schema_version": 1, "repeats": 2, "max_repair_rounds": 1, "timeout_seconds": 20,
        "check_timeout_seconds": 10, "order_seed": 42,
        "candidates": [
            {"id": "fixture-good", "adapter": "fixture", "responses": GOOD},
            {"id": "fixture-bad", "adapter": "fixture", "responses": BAD},
            {"id": "fixture-repair", "adapter": "fixture", "responses": {k: [BAD[k], GOOD[k]] for k in GOOD}},
        ], "judge": JUDGE,
    }
