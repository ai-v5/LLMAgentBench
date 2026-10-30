/* The overall source contains only authorized totals; token data is public synthetic only. */
(function () {
  "use strict";
  const PUBLIC = "results/engineering-public-r3/summary.json";
  const OVERALL = "results/engineering-overall-r3/summary.json";
  const TOKENS = "results/engineering-public-r3/token-usage.json";
  const states = ["passed", "failed", "unscored", "errors", "timeouts"];
  const number = (value) => typeof value === "number" && Number.isFinite(value);
  const count = (value) => Number.isInteger(value) && value >= 0;

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
        overallFinal: total.passed / total.assigned * 100, tokens };
    });
    return { rows };
  }

  function put(selector, value) {
    document.querySelectorAll(selector).forEach((node) => { node.textContent = String(value); });
  }

  function show(result) {
    result.rows.forEach((row, index) => {
      const attr = (name) => "[" + name + '="' + index + '"]';
      put(attr("data-name"), row.label);
      put(attr("data-public-first"), row.publicFirst.toFixed(1) + "%");
      put(attr("data-public-final"), "含修复 " + row.publicFinal.toFixed(1) + "%");
      put(attr("data-all-first"), row.overallFirst.toFixed(1) + "%");
      put(attr("data-all-final"), "含修复 " + row.overallFinal.toFixed(1) + "%");
      put(attr("data-token-rate"), row.tokens ? row.tokens.rate.toFixed(2) : "未记录");
      put(attr("data-token-detail"), row.tokens ? row.tokens.count + " tokens / " + row.tokens.seconds.toFixed(2) + " s" : "数据不完整");
    });
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { derive };
  if (typeof document !== "undefined") {
    (async () => {
      try {
        const responses = await Promise.all([fetch(PUBLIC, { cache: "no-cache" }), fetch(OVERALL, { cache: "no-cache" })]);
        if (responses.some((response) => !response.ok)) throw new Error("Summary unavailable");
        const [publicData, overallData] = await Promise.all(responses.map((response) => response.json()));
        try {
          const response = await fetch(TOKENS, { cache: "no-cache" });
          if (!response.ok) throw new Error("Token aggregate unavailable");
          show(derive(publicData, overallData, await response.json()));
        } catch (_) {
          document.getElementById("token-error").hidden = false;
          show(derive(publicData, overallData, null));
        }
      } catch (_) {
        document.getElementById("data-error").hidden = false;
      } finally {
        document.querySelectorAll("[data-data-region]").forEach((node) => node.setAttribute("aria-busy", "false"));
      }
    })();
  }
})();
