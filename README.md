# LLMAgentBench

面向真实工程工作的自动评估器：LLM 驱动任务，代码固定执行条件、验证结果并生成报告。首版支持 **Codex** 和 **DeepSeek Harness（DSH）headless**。

当前模式是 `response_patch`：候选返回答案和文件内容，由评估器应用修改并执行独立检查。完整终端操作、多人协作和长时间部署任务尚未实现，不能用 smoke 推断这些能力。

## 运行

Python 3.11+，运行时只有标准库。在仓库根目录执行，无需安装依赖。

```powershell
python -m llmagentbench validate --pack examples/public/pack.json
python -m llmagentbench run --pack examples/public/pack.json --config configs/fixture-smoke.json --out .bench-runs/demo
python -m llmagentbench report --run .bench-runs/demo
python -m llmagentbench export-public --run .bench-runs/demo --out results/demo
python -m pytest
```

夹具包含正确、错误和首次错误后修复的候选，用于测试评估器。它不是模型测量。pytest 是开发测试依赖。

真实 Codex 使用已有 CLI 登录状态：

```powershell
python -m llmagentbench run --pack examples/public/pack.json --config configs/codex.example.json --out .bench-runs/codex
```

DSH 安装与路由按本机已有配置准备。复制 `configs/dsh.example.json` 到忽略的 `local/`，填写实际 provider/model/profile。凭据仍由 DSH 原有配置管理。每次新建 headless 会话，用命令本地的 overlay 固定模型和只读策略，不操作已有会话。

```powershell
# 如 dsh 不在 PATH，变量内容为原生命令及入口参数组成的 JSON 数组。
$env:BENCH_DSH_LAUNCHER = '["C:/Tools/node.exe","C:/Tools/dsh/bin.js"]'
python -m llmagentbench run --pack examples/public/pack.json --config local/dsh.json --out .bench-runs/dsh
```

Windows Desktop 安装可用其原生 Electron 可执行文件和随附 CLI JS 入口，并设 `electron_run_as_node: true`；不使用 `.cmd`/`.bat` 或 shell 拼接。profile 必须预先准备，评估器不修改它。新会话会由 DSH 持久保存。

## 两仓边界

| 公开仓 | 独立私仓 |
|---|---|
| 执行器、评分器、合同、合成 case、测试、公开报告 | 非公开 case、输入、隐藏检查、私有运行结果 |

通过 `--pack` 指向独立私仓，无需 submodule、私有 remote 或把私有文件复制进公开仓。

```powershell
python -m llmagentbench run --pack ../private-cases/packs/example/pack.json --config local/matrix.json --out ../private-cases/.bench-runs/example
```

`export-public` 拒绝 private 或非合成 pack。私有结果不自动上传或转成公开汇总。

在用户明确授权公开总体数量和耗时时，可用 `export-overall` 合并完整运行：它只输出显式指定的公开候选名称、总体数量和耗时，不输出题目、题号、分类、私有 pack 元数据或原始收据。必须提供 `--allow-private-aggregate` 才能纳入私有运行；发布前仍需审查精确输出内容。

`examples/engineering/pack.json` 是合成工程案例，覆盖代码修改、问题排查、代码评审和性能分析。代码题限制在提示中列明的无导入 Python 子集，验收前检查语法树；这些案例仍不是完整终端 Agent 任务。

## 指标

- 确定性评分优先：JSON 匹配、数值容差、评估器持有的 Python 行为检查、修改路径约束。
- 主观部分用独立 LLM rubric；候选身份不进入评分提示。引用必须出现在输入或答案中，判断本身仍可能出错。
- 记录首次通过率、预算内通过率、失败/未知/错误/超时、修复轮数、运行时间和可用 token 计数。
- 有效吞吐是预算内通过数除以全部尝试的累计计时，再换算为每小时通过题数。累计计时从输入准备完成后开始，包含候选调用、CLI 内的网络与服务排队等待、自动检查、可选 LLM 评分和修复；不含输入准备、样本开始前的调度等待或人工核验。结果同时列出候选调用和 LLM 评分器调用的总耗时，不代表并发服务吞吐。
- `human_minutes` 固定为 `null + NOT_MEASURED`；自动修复不能冒充实测人工核验时间。
- 未知费用保留 `null`，当前不能生成美元成本排名。

合成题只验证链路；真实选型需要代表性的未见任务、重复运行、评分器校准和足够样本。重复与修复不会被当作 best-of-N 后只报最好成绩。

更多说明：[执行与评分合同](docs/CONTRACTS.md)、[LLM 操作指南](docs/LLM_WORKFLOW.md)、[接口来源](docs/SOURCES.md)。
