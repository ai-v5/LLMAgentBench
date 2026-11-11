# 运行与发布规范

本文件是给"另一台机器/另一个 agent"的契约：按这里跑，按这里更新站点。执行前先读 `docs/CONTRACTS.md`。

## 0. 题库组成（版本 20261111）

| 位置 | 文件 | 内容 |
|---|---|---|
| 公开仓 | `pack.json`（`version: 20261111`，13 题） | 公开题索引，用于公开结果与公开绘图展示 |
| 私仓 | `packs/suite-20261111/pack.json`（91 题） | 全量套件：私仓所有唯一 case + 公开 13 题副本，单次运行覆盖全部题 |

- 全量套件由私仓 `scripts/build_suite.py --version 20261111 --public-pack <公开仓 pack.json>` 生成；内容变更时须使用新版本，避免覆盖已有套件。
- 套件按 case id 去重：同一 id 出现在多个旧 pack 时，取 `version` 最高的来源。
- 题目输入及检查脚本复制到套件目录，不依赖原始源码仓库的工作区。总体评测包含固定源码片段，不能标为纯合成；公开题包仍为合成题。分类更正不修改题目内容，但会改变输入指纹。
- 公开结果来自公开 `pack.json` 的运行；总体结果 = 公开运行 + 套件中非公开部分的运行，合并导出时不得暴露私有 case。
- 两处 `version` 必须同时变更。

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

每个模型固定跑 `low`、`high`、`max` 三个 `reasoning_effort`（服务端只保证这三档；`xhigh` 仅在模型声明支持时使用）；同一批次内 pack 版本、执行器、judge、预算必须一致。

### 2.2 题包与预算

| 用途 | 题包 | repeats | repair | timeout |
|---|---|---:|---:|---:|
| 公开题 | `pack.json`（13 题） | 2 | 1 | 600 s |
| 全量套件 | 私仓 `packs/suite-20261111/pack.json`（91 题） | 1 | 1 | 600 s |
| 混合总体 | 公开 13 + 私有 16 + 8 个 admitted ALE（见私仓） | 各 2 / ALE 1 | 1 | 600 / ALE 420 |

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
4. `provenance.json` / `overall-provenance.json`：与 `results/terra-20261110-standard/<effort>/` 同构；新批次统一放在 `results/exp-<version>/<模型简写>/<effort>/`。

public 与 overall 的 `label` 必须一致，且等于 `"<显示名> <effort>"`（如 `"DSH V4.1 Flash 1017 Flex low"`）；行首另显示 `题库 <pack_version>`，无版本的历史行显示「未标注」。

公开 provenance 按完整 case 复用时，各来源的 `selected_cases` 之和等于公开题数；按 case 与 repeat 分别复用时，使用 `selection_granularity: "case_repeat"`，各来源的 `selected_assignments` 之和必须等于 `case_count * repeats`。每个来源仍须是已完成的公开合成运行，核验题目、检查脚本、模型、强度与收据，并防止重复计数；不得输出私有逐题明细。历史收据无法重新核验时，必须保留来源发布提交和核验边界，不能标记为本次已重新核验。

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

## 5. 已退役的模型

`ds-v4.1-flash-1017`（非 flex）自 2026-11-11 起不再出现在 18900 端点的 `/v1/models` 中，历史行已从结果表删除，
其旧结果目录 `results/engineering-1017-efforts/` 已移除；替代模型 `ds-v4.1-flash-1017-flex` 的结果在
`results/exp-20261111/flex/`。若该模型重新部署，用站点 `BATCHES` 的 `effort` 映射加回三行即可，不要复用旧数据。
