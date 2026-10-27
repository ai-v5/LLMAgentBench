# 评估结果

Run: `fixture-smoke-r2` · state: `completed`

自动验收与修复指标；人工核验时间未测量。合成 smoke 不能作为模型排名。

| 候选 | 证据 | 样本 | 首次通过率 | 预算内通过率 | 失败/未知/错误/超时 | 平均耗时(s) |
|---|---|---:|---:|---:|---|---:|
| fixture-good | FIXTURE_SMOKE | 8 | 100.0% | 100.0% | 0/0/0/0 | 0.018 |
| fixture-bad | FIXTURE_SMOKE | 8 | 0.0% | 0.0% | 8/0/0/0 | 0.029 |
| fixture-repair | FIXTURE_SMOKE | 8 | 0.0% | 100.0% | 0/0/0/0 | 0.033 |

Pack SHA256: `10c0df355b113daef241f31077946cb55f36fbf3796baaa902a399af200331f2`

Engine SHA256: `f6b471824a3f76c99b752398fa3165d82890b50d95375f66f2932079379185db`

成本未知时为 null；费用不由模型猜测。通过率包含全部分配样本；修复轮次不是独立样本。
