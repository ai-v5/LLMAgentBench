/* The overall source contains only authorized totals; token data is public synthetic only. */
(function () {
  "use strict";
  const BATCHES = [
    { public: "results/engineering-public-r3/summary.json", overall: "results/engineering-overall-r3/summary.json",
      tokens: "results/engineering-public-r3/token-usage.json", offset: 0,
      models: { "Codex GPT-6.1 Terra": "gpt-6.1-terra", "DSH V4.1 Flash 1017": "ds-v4.1-flash-1017" } },
    { public: "results/engineering-public-luna-sol-r1/summary.json", overall: "results/engineering-overall-luna-sol-r1/summary.json",
      tokens: "results/engineering-public-luna-sol-r1/token-usage.json",
      comparison: "results/engineering-public-luna-sol-r1/comparison.json", offset: 2,
      models: { "Codex GPT-6.1 Sol": "gpt-6.1-sol", "Codex GPT-6 Luna": "gpt-6-luna" } },
  ];
  const states = ["passed", "failed", "unscored", "errors", "timeouts"];
  const number = (value) => typeof value === "number" && Number.isFinite(value);
  const count = (value) => Number.isInteger(value) && value >= 0;
  const sortData = new Map();
  let currentSort = null;

  function validate(summary) {
    if (!summary || summary.schema_version !== 1 || !Number.isInteger(summary.case_count) || summary.case_count < 1 ||
        !Number.isInteger(summary.repeats) || summary.repeats < 1 ||
        !Array.isArray(summary.candidates) || summary.candidates.length !== 2) throw new Error("Invalid summary");
    for (const row of summary.candidates) {
      if (!row || typeof row.label !== "string" || !row.label.trim() || row.evidence !== "MODEL_RUN" ||
          !Number.isInteger(row.assigned) || row.assigned !== summary.case_count * summary.repeats ||
          !count(row.first_passed) || states.some((key) => !count(row[key])) ||
          states.reduce((sum, key) => sum + row[key], 0) !== row.assigned || row.first_passed > row.passed ||
          !number(row.attempt_seconds) || row.attempt_seconds <= 0 ||
          !number(row.candidate_call_seconds) || row.candidate_call_seconds < 0 ||
          !number(row.judge_call_seconds) || row.judge_call_seconds < 0 ||
          row.candidate_call_seconds + row.judge_call_seconds > row.attempt_seconds + .01 ||
          !number(row.mean_attempt_seconds) || Math.abs(row.mean_attempt_seconds - row.attempt_seconds / row.assigned) > .001 ||
          !number(row.effective_passes_per_hour) ||
          Math.abs(row.effective_passes_per_hour - row.passed * 3600 / row.attempt_seconds) > .001) {
        throw new Error("Invalid candidate summary");
      }
    }
    if (new Set(summary.candidates.map((row) => row.label)).size !== summary.candidates.length) throw new Error("Duplicate candidate");
  }

  function derive(publicData, overallData, usage) {
    validate(publicData);
    validate(overallData);
    if (publicData.repeats !== overallData.repeats || publicData.case_count > overallData.case_count) {
      throw new Error("Incompatible score summaries");
    }
    if (usage && (usage.schema_version !== 2 || usage.case_count !== publicData.case_count ||
        usage.repeats !== publicData.repeats || !Array.isArray(usage.source_receipt_sha256) ||
        !usage.source_receipt_sha256.length || !usage.source_receipt_sha256.every((value) => /^[a-f0-9]{64}$/.test(value)) ||
        !Array.isArray(usage.candidates) || usage.candidates.length !== publicData.candidates.length ||
        new Set(usage.candidates.map((row) => row.label)).size !== usage.candidates.length)) {
      throw new Error("Invalid public token aggregate");
    }
    const rows = publicData.candidates.map((item) => {
      const total = overallData.candidates.find((row) => row.label === item.label);
      if (!total || item.assigned > total.assigned || item.first_passed > total.first_passed ||
          states.some((key) => item[key] > total[key])) {
        throw new Error("Incompatible candidate summaries");
      }
      let tokens = null;
      if (usage) {
        const row = usage.candidates.find((entry) => entry.label === item.label);
        if (!row || row.evidence_level !== "MODEL_RUN" || !["codex", "dsh"].includes(row.adapter) ||
            row.assigned !== item.assigned || !count(row.candidate_calls) || !count(row.usage_calls) ||
            row.usage_calls > row.candidate_calls || !number(row.candidate_call_seconds) ||
            Math.abs(row.candidate_call_seconds - item.candidate_call_seconds) > .001 ||
            (row.output_tokens !== null && (!count(row.output_tokens) || row.candidate_calls === 0 ||
             row.usage_calls !== row.candidate_calls || row.candidate_call_seconds <= 0))) {
          throw new Error("Invalid candidate token aggregate");
        }
        if (row.output_tokens !== null) {
          tokens = { count: row.output_tokens, seconds: row.candidate_call_seconds, rate: row.output_tokens / row.candidate_call_seconds };
        }
      }
      return { label: item.label, publicFirst: item.first_passed / item.assigned * 100,
        publicFinal: item.passed / item.assigned * 100, overallFirst: total.first_passed / total.assigned * 100,
        overallFinal: total.passed / total.assigned * 100,
        publicIssues: [item.unscored, item.errors, item.timeouts],
        overallIssues: [total.unscored, total.errors, total.timeouts], tokens };
    });
    return { rows };
  }

  function put(selector, value) {
    document.querySelectorAll(selector).forEach((node) => { node.textContent = String(value); });
  }

  function validateComparison(value) {
    const flags = ["same_pack_order", "same_assignment_order", "same_engine", "same_driver", "same_budget", "same_judge_configuration"];
    if (!value || value.schema_version !== 1 || flags.some((key) => value[key] !== true) ||
        typeof value.same_judge_executable !== "boolean" || !Array.isArray(value.requested_models) ||
        value.requested_models.slice().sort().join(",") !== ["gpt-6-luna", "gpt-6.1-sol"].sort().join(",")) {
      throw new Error("Suite comparison unavailable");
    }
  }

  function sortRows() {
    if (!currentSort) return;
    const body = document.querySelector(".results-table tbody");
    const rows = Array.from(body.querySelectorAll("tr[data-result-row]"));
    const value = (row) => {
      const data = sortData.get(Number(row.getAttribute("data-result-row")));
      if (!data) return null;
      return currentSort.key === "tokens" ? (data.tokens ? data.tokens.rate : null) : data[currentSort.key];
    };
    rows.sort((a, b) => {
      const left = value(a), right = value(b);
      const original = Number(a.getAttribute("data-result-row")) - Number(b.getAttribute("data-result-row"));
      if (left == null || right == null) return left == null && right == null ? original : left == null ? 1 : -1;
      const comparison = typeof left === "string" ? left.localeCompare(right, "en", { numeric: true, sensitivity: "base" }) : left - right;
      return (currentSort.direction === "ascending" ? comparison : -comparison) || original;
    });
    rows.forEach((row) => body.appendChild(row));
  }

  function show(result, offset) {
    const finalText = (rate, issues) => "含修复 " + rate.toFixed(1) + "%" +
      (issues.some((value) => value > 0) ? " · 未评分/错误/超时 " + issues.join("/") : "");
    result.rows.forEach((row, position) => {
      const index = position + offset;
      const attr = (name) => "[" + name + '="' + index + '"]';
      put(attr("data-name"), row.label);
      put(attr("data-public-first"), row.publicFirst.toFixed(1) + "%");
      put(attr("data-public-final"), finalText(row.publicFinal, row.publicIssues));
      put(attr("data-all-first"), row.overallFirst.toFixed(1) + "%");
      put(attr("data-all-final"), finalText(row.overallFinal, row.overallIssues));
      put(attr("data-token-rate"), row.tokens ? row.tokens.rate.toFixed(2) : "未记录");
      put(attr("data-token-detail"), row.tokens ? row.tokens.count + " tokens / " + row.tokens.seconds.toFixed(2) + " s" : "数据不完整");
      sortData.set(index, row);
      document.querySelector(attr("data-result-row")).hidden = false;
    });
    sortRows();
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { derive };
  if (typeof document !== "undefined") {
    const sortButtons = document.querySelectorAll("[data-sort-key]");
    sortButtons.forEach((button) => button.addEventListener("click", () => {
      const key = button.dataset.sortKey;
      const direction = currentSort && currentSort.key === key
        ? (currentSort.direction === "ascending" ? "descending" : "ascending")
        : (key === "label" ? "ascending" : "descending");
      currentSort = { key, direction };
      sortButtons.forEach((control) => control.closest("th").removeAttribute("aria-sort"));
      button.closest("th").setAttribute("aria-sort", direction);
      sortRows();
    }));
    async function loadBatch(batch) {
      try {
        if (batch.comparison) {
          const provenance = await fetch(batch.comparison, { cache: "no-cache" });
          if (!provenance.ok) throw new Error("Suite comparison unavailable");
          validateComparison(await provenance.json());
        }
        const responses = await Promise.all([fetch(batch.public, { cache: "no-cache" }), fetch(batch.overall, { cache: "no-cache" })]);
        if (responses.some((response) => !response.ok)) throw new Error("Summary unavailable");
        const [publicData, overallData] = await Promise.all(responses.map((response) => response.json()));
        if (!Array.isArray(publicData.candidates) || publicData.candidates.length !== Object.keys(batch.models).length ||
            publicData.candidates.some((row) => !Object.hasOwn(batch.models, row.label))) {
          throw new Error("Unexpected candidate labels");
        }
        let usage;
        try {
          const response = await fetch(batch.tokens, { cache: "no-cache" });
          if (!response.ok) throw new Error("Token aggregate unavailable");
          usage = await response.json();
        } catch (_) {
          document.getElementById("token-error").hidden = false;
          show(derive(publicData, overallData, null), batch.offset);
          return;
        }
        if (!Array.isArray(usage.candidates) || usage.candidates.some((row) => batch.models[row.label] !== row.requested_model)) {
          throw new Error("Token aggregate model identity mismatch");
        }
        try {
          show(derive(publicData, overallData, usage), batch.offset);
        } catch (_) {
          document.getElementById("token-error").hidden = false;
          show(derive(publicData, overallData, null), batch.offset);
        }
      } catch (_) {
        document.getElementById("data-error").hidden = false;
      }
    }
    Promise.all(BATCHES.map(loadBatch)).finally(() => {
      document.querySelectorAll("[data-data-region]").forEach((node) => node.setAttribute("aria-busy", "false"));
    });
  }
})();
