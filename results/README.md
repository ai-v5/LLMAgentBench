# 结果说明

本目录只包含公开合成输入的脱敏汇总。它们验证执行链路，不代表模型排名或实测人工节省。

- `fixture-smoke-r2`、`fixture-smoke-r3`、`fixture-smoke-r4`：评估器自身的正、负及修复对照，不是模型运行。不同目录保留各自的引擎指纹。
- `native-smoke-r4`：Codex 和 DSH 的完整四题合成 smoke。DSH 的一项保留为格式错误：该版本未解析单个 Markdown JSON 代码块。结果保持原始状态，未事后改分。
- `dsh-explanation-r5`：修复解析器后，对同一道说明题重新执行的单项 DSH smoke。它与完整四题运行采用不同引擎版本及 pack，不应合并计算通过率或比较排名。

每份 summary 包含 pack 和引擎 SHA256；模型字段是请求值，服务端实际模型版本若未被观测则保持未知。私有 case 的输入、明细和结果不在本目录。
