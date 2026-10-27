# 接口来源与边界

- [Codex 非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)：exec、JSON 事件与输出 schema。实现同时核对本机 exec --help。
- [Codex 自动修复示例](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex)：结构化结果与分离验证。
- [DSH CLI](https://github.com/deepseek-ai/deepseek-harness/tree/main/apps/cli)：profile 和 invocation-local patch。
- [DSH headless](https://github.com/deepseek-ai/deepseek-harness/tree/main/packages/bundle/headless)：fresh session、JSON 事件、final 和完成终态。使用原生命令，不复制其实现。
- [METR 测量限制](https://metr.org/blog/2026-02-24-uplift-update/)：自动时间、任务选择和并行会干扰人工生产力推断。本项目不自动生成实测节省人力结论。

当前只验证已披露的环境和样例，不宣称全版本或全平台兼容。
