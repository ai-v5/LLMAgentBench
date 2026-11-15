# 执行与评分合同 v1

## 范围

公开代码和合成样例，独立私仓提供非公开 case。支持 Codex、DSH headless 和 Kimi Daimon prompt；fixture 是评估器测试替身。标准化任务输入、文件修改协议、轮次预算和验收。三个原生代理的系统提示、工具、认证和服务端行为不同，不能声称只比较裸模型。默认 `response_patch` 中，Codex 使用 output schema 约束输出并忽略用户配置；DSH 使用 headless profile 和提示要求 JSON；Kimi 使用本机 Daimon 非交互 prompt、提示要求 JSON 并审计 wire 事件，因此格式和工具约束强度不同，这个差异包含在组合结果里。

## Case pack

pack.json 使用 schema_version: 1，要求唯一 id、visibility（public/private）、显式 synthetic 布尔值、非空 cases 相对路径列表。purpose 标注 candidate、smoke 或 benchmark；candidate 不代表题目已通过独立质量验证。

新题包可用 `evaluation_scope` 标记 `engineering`、`hash` 或 `diagnostic`，该字段进入题包指纹、运行收据和本地汇总。历史收据没有该字段时保持未知。总体导出和按题复用拒绝混合不同范围，或将范围已知与未知的收据混合；两个都未标注的历史来源仍按原合同处理。

可选的 `case_families` 必须覆盖题包中每道题，且每题恰好映射到一个题族。收据保留该映射和每次尝试的题族；本地报告除按题计数外，还列出各题族状态与题族等权通过率，避免同族变体过多时只看按题汇总。题族等权是候选统计口径，不代表用户实际工作频率，也不能替代独立留出集或重复试跑。旧收据未标题族时不补猜。当前按题复用不支持题族映射，会明确拒绝而非丢掉分组。

`invocation_mode` 默认是 `response_patch`；`workspace_tools` 是 Codex/DSH 的候选或 smoke 模式，不能与默认模式混合汇总或复用结果。工具模式将输入写入独立工作区并只在提示中列出文件名，允许直接修改、运行代码及访问公开网页；初始输入中未列入 `allowed_write_paths` 的文件受保护，新建的工作文件允许存在。每轮评分前固化工作区文件及其摘要，读取收据时核对快照；评分器改变工作区则该轮未评分。DSH 启动参数中额外的 `--patch` 文件以摘要绑定，工具模式要求其为绝对路径。早期没有快照的工具试跑保留为历史诊断，不得公开导出或复用成绩。工具事件只保存计数和类型，不保存参数或输出；工具或网络是否可用须以实际运行核验，事件计数不是完整行为追踪。Codex 已执行命令的普通非零退出不单独算作工具错误；126、127、137 和 Windows 9009 等可能对应环境或资源故障的退出码，以及拒绝、无法判定原因的客户端错误，仍保守记录，不能据此认定根因。若验收失败且客户端报告过工具错误或上述不确定情况，评分器失败保留为原始信息、该轮保守记为未评分；通过的验收不因此前工具错误而降级。

每个 case 有唯一 id、category、prompt、字符串文件映射 inputs、允许修改的精确相对路径列表 allowed_write_paths、非空 checks。相对路径使用 `/`，拒绝绝对路径、上级跳转、盘符、`.git`、符号链接和 junction。输入逐字写入新的工作目录，候选之间不共享目录。

默认模式的候选收到 prompt、inputs、允许修改路径，以及修复时的旧输出/检查 ID 和状态。工具模式提供任务与工作区输入路径。expected、rubric 和 Python 验收脚本由评估器保留，不复制进候选工作目录。这是输入分离，不是对恶意程序的保密沙盒保证。

默认模式候选提交 `{answer, files}`。answer 可为文本或 JSON 对象；Codex 输出 schema 要求先编码成字符串。DSH 的完整 JSON 可以置于单个 Markdown 代码块内；代码块前后不能包含其他内容。Kimi 必须输出一个只含 `answer`、`files` 两个键的 JSON 对象，`answer` 必须是字符串，`files` 中每项必须只含 `path`、`content`；适配器只移除明确的 Daimon 运行日志并允许合法多行 JSON，不接受代码围栏、前后夹杂文本或多个 JSON。格式不合格计为该 case 失败。files 是 `{path, content}` 数组，评估器只允许清单内路径。默认模式未列出文件、受保护输入或非法路径发生修改，样本失败并停止自动修复。工具模式由候选直接在工作区操作并返回普通最终答复；验收独立检查工作区和实际产物。

## 评分

所有检查 mandatory。JSON 匹配区分 false 与 0；数字拒绝 bool 和非有限数。Python 检查由 pack 提供的可信脚本执行，参数为工作目录；脚本必须正常返回、进程退出 0 并由执行包装器确认检查已运行结束，提前退出不能算通过。检查超时为 unknown，不伪装成模型答错。

代码检查未通过时不花费 LLM 评分预算。LLM rubric 需要独立 judge；缺失、调用失败、无效 JSON 或不存在的引用为 unknown。judge 返回 `{verdict, reason, evidence:[{source,quote}]}`，source 只能是 answer 或输入文件名。代码校验引用存在，不证明解释正确。单 judge 可能有偏差，需用已知好坏答案校准，不能覆盖代码检查失败。

outcome：全部通过为 pass；存在失败为 fail；有未知且无失败为 unscored；适配器异常为 error；调用超时为 timeout。error/timeout/unscored 不自动无限重试。

## 一致性与终态

配置固定 repeats、max_repair_rounds、每轮 timeout_seconds、每项 Python 检查 check_timeout_seconds、候选、judge 和顺序随机种子。每次重复为独立样本；自动修复仍属于同一样本。候选最多调用 `1 + max_repair_rounds` 次。原生代理内部重试仍属于代理实现，当前不能保证两边内部调用次数相同。

pack 指纹覆盖 manifest、case 和检查脚本；运行时检查脚本改变则该项为 unknown。记录引擎源码 SHA256、候选配置 SHA256、CLI 身份、Python/平台与模型请求值。运行中引擎、候选或 judge 身份改变时，run 标记 invalidated，不得作为完整结果导出。DSH 记录 profile 指纹，临时 overlay 固定 provider/model/reasoning 和只读策略，不改变原 profile；Kimi 记录 launcher、配置文件哈希、model/reasoning wire 字段和工具事件审计状态，不保存 wire 原文。Daimon 已知会异步改写配置文件时，候选可提供启动时计算的 `config_identity_sha256` 作为本次运行的冻结配置身份；配置路径仍必须存在。请求模型不等于服务端实际模型，无法观察时 observed_model 为 null。

每轮、样本和 run manifest 有内容指纹；report/export 重新验证层级收据与样本矩阵。已有 run/export 目录拒绝覆盖。中断保留 running，不能作为 completed 导出。哈希检查不一致，不是数字签名，也不能对抗拥有整个文件系统写权限的攻击者。

## 统计与发布

通过率分母为全部分配样本，包含失败、未知、错误和超时；按任务类型分开统计。首次通过与修复后通过分开。修复次数、调用量、耗时是代理指标，不是人工时间。fixture 与真实候选或 judge 混合时，该行仍标 FIXTURE_SMOKE。

原始输出与收据留在 `.bench-runs/` 或私仓。公开导出只接受完整 public + synthetic run，以字段 allowlist 生成汇总，不复制原始回答、提示、工作目录、session 日志和机器配置。发布由显式命令触发。

用户明确授权公开总体数量与耗时时，可使用独立的 `export-overall` 命令合并完整运行。必须显式传入 `--allow-private-aggregate` 和公开候选名称映射；同一引擎、配置和候选身份才可合并，重复运行或题包拒绝计数。导出只包含总体题数、各公开名称对应的总体状态计数和耗时，不包含私有题号、题目、类别、源码、题包或收据身份。该命令不会自动 push；每次公开提交前仍需核对精确内容。

## 执行边界

默认模式的 Codex/DSH 使用原生只读策略，通过响应提交文件。工具模式请求 `workspace-write` 并允许工具；不得用禁用工具的 `local_lookup_audit` 运行该模式。Kimi 使用 Daimon prompt mode，并要求 wire 审计没有报告工具调用；Kimi 不支持工具模式。Codex 调用显式关闭记忆注入与记忆生成；沿用用户 Codex 目录时，全局 `AGENTS.md` 仍可能注入。收据记录的是配置而非实际隔离结果。DSH 的工作区写策略不限制所有文件读取；需要严格隔离时必须在独立环境实测并隔离整个执行器。Python 行为检查会执行候选代码，目录分离不是操作系统沙盒。本机只运行可信来源的合成 case；外部不可信 case/代码应在独立 VM/容器中执行整个评估器。当前不实现恶意代码隔离、网络封锁、资源配额、多 writer、崩溃恢复或生产调度。
