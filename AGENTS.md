# LLMAgentBench

- This is a public repository. Use synthetic inputs only. Private cases and private results belong in a separate private repository.
- Develop in an independent worktree. Preserve existing changes. Explicitly stage only task files.
- Scope: Codex and DSH headless adapters. Fixture adapters test this evaluator and must remain labelled `FIXTURE_SMOKE`.
- The evaluator owns case inputs, grading scripts, budgets, order, receipts and result aggregation. Candidate output must never define its own pass/fail status.
- Run `python -m pytest` after logical changes. Include negative controls for changes to scoring, isolation, export or receipt integrity.
- Missing grades are `unscored`; failed, errored and timed-out attempts stay in the denominator. First-attempt success and success after automatic repair are separate metrics.
- Automated repair effort is a proxy. Never infer measured human minutes, labor savings or a production ranking from synthetic smoke cases.
- Public export is explicit, aggregate-only, and restricted to completed public synthetic packs. Never automatically export private results.
- Run artifacts and machine-specific configuration stay under ignored `local/` or `.bench-runs/`. Credentials stay in existing authentication stores or process environment, never in cases, logs or result files.
