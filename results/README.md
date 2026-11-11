# 结果说明

本目录包含公开合成输入的汇总，以及用户明确授权公开的混合题库总体计数和耗时。它们不代表完整模型排名或实测人工节省。

- `fixture-smoke-r2`、`fixture-smoke-r3`、`fixture-smoke-r4`：评估器自身的正、负及修复对照，不是模型运行。不同目录保留各自的引擎指纹。
- `native-smoke-r4`：Codex 和 DSH 的完整四题合成 smoke。DSH 的一项保留为格式错误：该版本未解析单个 Markdown JSON 代码块。结果保持原始状态，未事后改分。
- `dsh-explanation-r5`：修复解析器后，对同一道说明题重新执行的单项 DSH smoke。它与完整四题运行采用不同引擎版本及 pack，不应合并计算通过率或比较排名。
- `terra-1017-public-r1`：Terra/Codex 与 DSH 1017 在四道公开合成题各重复三次的历史 smoke（该模型已于 2026-11-11 下线，行已从站点删除）；执行时引擎对应提交 `462bbf77c2ed0e5e33c4678fc60b89287ec0f478`。报告在修正计时说明后由原始收据重新渲染，数值未改。单次实验不代表完整 Agent 能力或稳定排名。
- `engineering-overall-r3`：经用户授权公开的混合题库总体汇总，23 道题每题重复两次，候选均请求 `max` 推理、每轮最多 240 秒，最多自动修复一次；执行时评估器代码对应提交 `d5ea32cbc03d4929c264761691c0ae7000a8e956`。这是结构化响应与补丁测试，模型服务端实际身份及人工核验时间未观测；两个原生执行器的输出约束不同，结果不代表完整终端 Agent 排名或并发服务吞吐。
- `engineering-public-r3`：同一轮中公开合成题的总体汇总及候选输出 token 汇总；不包含裁判 token、逐题结果或私有题信息。输出 token 总数除以候选调用总耗时，包含客户端及等待开销，不是服务端解码速率。
- `engineering-public-luna-sol-r1` 和 `engineering-overall-luna-sol-r1`：Sol 与 Luna 的公开合成题汇总及经授权的全部题目总体汇总。题包、派题顺序、评测引擎、套件驱动、预算和裁判配置与 `engineering-overall-r3` 一致；Codex 客户端执行文件不同，模型服务端实际身份未观测。公开题 token 统计只包含候选调用。部分题目使用 Sol 裁判，Sol 候选存在同模型评分偏差的可能。
- `engineering-overall-case-retest-r1`：经核验的四个组合总体汇总及条件核验信息，不包含私有题身份或逐题、分类数据。
- `engineering-overall-ale-r1`：经授权的最新总体汇总；按实际分配尝试计算得分，不包含私有题身份、内容或逐题结果。
- `engineering-kimi-public-r1`：Kimi K3.1 Pro 在公开 synthetic engineering pack 上的公开聚合与候选 output token 汇总；不包含逐题结果。
- `exp-20261111`：题库版本 `20261111` 的公开题与总体聚合。公开题来自 `pack.json`（13 题），总体包含私仓 78 题（共 91 题）但只发布聚合计数。每个模型 × 档位一个子目录，含 `summary.json`、`overall.json`、`token-usage.json`、`provenance.json`、`overall-provenance.json`；矩阵以最多 6 路并行执行，超时与适配器错误按题串行重跑一次，使用重跑的档位在 provenance 标记 `mixed_conditions` 并列出全部来源收据。
- `engineering-kimi-overall-r1`：经用户授权的 Kimi 私有题库总体计数与耗时聚合；不包含私有题身份、内容、题包元数据、逐题结果或原始收据。
- `public-benchmark-v1`（pack）后续修订：`quality-rate` 明确 elapsed 计入所有 status，`wss-proxy-triage` 明确 `UNKNOWN` 的判定规则；新增 `crocodile-bike`（HTML/SVG 绘图）。16 道高难度题位于独立私仓，题名与内容不在本仓公开，只发布其总体计数。上列所有基于旧口径或旧 pack 的结果不可与修订后的 pack 逐位比较。

公开合成题的单包 summary 包含 pack 版本、pack 和引擎 SHA256；版本规则见 docs/RUNBOOK.md（YYYYMMDD，同日多次修改加 -vN）；混合题库只展示总体数量和耗时，不包含私有题包标识或逐题、分类数据。模型字段是请求值，服务端实际模型版本若未被观测则保持未知。私有 case 的输入和明细不在本目录。
