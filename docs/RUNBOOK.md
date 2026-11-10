# 运行与发布规范

本文件是给"另一台机器/另一个 agent"的契约：按这里跑，按这里更新站点。执行前先读 `docs/CONTRACTS.md`。

## 1. 题库版本

- 每个 pack 的 `pack.json` 必须有 `version` 字段：`YYYYMMDD`（当天第一版）或 `YYYYMMDD-vN`（同一天第 N 次修改，N 从 2 开始）。
- 任何 case、检查脚本、controls、pack 列表的修改，都必须在同一次提交里 bump 版本：

  ```powershell
  python scripts/pack_version.py --pack pack.json --bump
  ```

- 版本号会进入 `pack_sha256` 的计算，并记录到 run 的 `manifest.json`、`summary.json`（`pack_version`）和报告里。
- **新运行必须用当前最新版本**；旧版本结果保留原身份，不覆盖、不合并进同一行。
- 版本字段引入前的历史结果可按其使用的快照日期回填 `pack_version`，但必须在 provenance/报告里注明“回填”，并以 `pack_sha256` 为权威身份。
- 同一张结果表可以混多个题库版本，但每一行必须显示自己的版本。

## 2. 测试规范

### 2.1 矩阵

每个模型固定跑 `low`、`high`、`xhigh`、`max` 四个 `reasoning_effort`；同一批次内 pack 版本、执行器、judge、预算必须一致。

### 2.2 题包与预算

| 用途 | 题包 | repeats | repair | timeout |
|---|---|---:|---:|---:|
| 公开题 | `pack.json`（当前 29 题，唯一索引） | 2 | 1 | 600 s |
| 混合总体 | 公开 `pack.json` + 8 个 admitted ALE pack（见私仓） | 公开 2 / ALE 1 | 1 | 公开 600 / ALE 420 |

- judge：`codex` / `gpt-6.1-sol` / `reasoning_effort: low`（仅含 `llm_rubric` 的题需要）。
- 运行命名：`<model>-<effort>-<pack_version>-r1`；产物放 `.bench-runs/`（公开仓忽略）或私仓忽略目录，**不要提交到公开仓**。
- 每档之间不要并发跑；并发会放大超时，超时类证据必须串行复测才算数。

### 2.3 命令

```powershell
python -m llmagentbench validate --pack pack.json
python -m llmagentbench run --pack pack.json --config local/<model>-<effort>.json --out .bench-runs/<model>-<effort>-<version>
python -m llmagentbench report --run .bench-runs/<model>-<effort>-<version>
```

配置骨架：

```json
{
  "schema_version": 1, "repeats": 2, "max_repair_rounds": 1,
  "timeout_seconds": 240, "check_timeout_seconds": 15, "order_seed": 42,
  "candidates": [{"id": "codex-<model>-<effort>", "adapter": "codex",
                  "model": "gpt-6.1-terra", "reasoning_effort": "max"}],
  "judge": {"adapter": "codex", "model": "gpt-6.1-sol", "reasoning_effort": "low"}
}
```

### 2.4 绘图题

`crocodile-bike` 同样按四个档位各跑一次，保存 `crocodile.html`，并抽取其中的 `<svg>` 供站点展示：

```powershell
python -m llmagentbench run --pack .bench-runs/croc-pack.json --config local/<model>-<effort>.json --out .bench-runs/<model>-<effort>-croc
```

## 3. 站点更新规范

### 3.1 每个（模型 × effort × 题库版本）一行

需要四个文件（放在 `results/<batch>/`）：

1. `public-<effort>.json`：schema 1，`case_count`=公开题数，`repeats`=2，`candidates[].assigned = case_count*repeats`；含 `pack_version`。
2. `overall-<effort>.json`：schema 2，`denominator: "assigned_attempts"`，含 `pack_version`。
3. `tokens-<effort>.json`：schema 2，`case_count/repeats` 与 public 一致，`source_receipt_sha256` 为公开 run 的收据哈希。
4. `provenance.json` / `revision.json`：与现有 `results/engineering-1017-efforts/` 同构。

public 与 overall 的 `label` 必须一致（如 `"DSH V4.1 Flash 1017 · low"`）；token 的 `requested_model` 必须与 `models` 映射一致。

### 3.2 页面

1. `site/app.js` 的 `BATCHES` 增加一个批次（public/overall/tokens/revision/overall_provenance/offset/models），offset 为现有行数。
2. `index.html` 预置对应行：`data-result-row`、`data-name`、`data-public-first/final`、`data-all-first/final`、`data-token-rate/detail`、`data-pack`。
3. 行首列显示 `请求模型 · <effort>` 和 `题库 <pack_version>`（无版本的历史行显示"未标注"）。
4. 绘图：在 `site/gallery.json` 增加 `{id,label,effort,svg,note}`，SVG 放 `site/artifacts/crocodile/`；**禁止** `<script>`、`foreignObject`、事件属性和外链，`tests/test_gallery.py` 会校验。
5. 不同题库版本放同一张表，不新建表；排序时按现有列。

### 3.3 校验与合并

```powershell
python -m pytest
node tests/site_contract.test.cjs
python -m llmagentbench validate --pack pack.json
```

- 新运行必须是完整 receipt；缺失的尝试按 unscored/error/timeout 计入分母。
- 私有题目的总体计数需要明确授权；公开仓只放聚合，不放题号、题目内容或逐题明细。
- 变更通过 PR 合并；不要把 `.bench-runs/`、`local/`、凭据或原始输出提交进公开仓。

## 4. 检查清单

- [ ] `pack.json` 的 `version` 已 bump，且与本次运行记录一致
- [ ] 四个 effort 全部完成，串行运行
- [ ] summary 含 `pack_version`，public/overall label 一致
- [ ] `pytest` 与 site contract 测试通过
- [ ] 新增 SVG 通过 inert 校验
- [ ] 隐私/凭据/原始输出未进入公开仓
