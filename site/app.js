/* The only numeric source is the explicitly authorized public aggregate. */
(function () {
  "use strict";

  const SOURCE = "results/engineering-overall-r3/summary.json";
  const states = ["passed", "failed", "unscored", "errors", "timeouts"];
  const number = (value) => typeof value === "number" && Number.isFinite(value);

  function derive(data) {
    if (!data || data.schema_version !== 1 || !Number.isInteger(data.case_count) || data.case_count < 1 ||
        !Number.isInteger(data.repeats) || data.repeats < 1 || !Array.isArray(data.candidates) || data.candidates.length !== 2) {
      throw new Error("Invalid aggregate");
    }
    const rows = data.candidates.map((item) => {
      if (!item || typeof item.label !== "string" || !item.label.trim() || item.evidence !== "MODEL_RUN" ||
          !Number.isInteger(item.assigned) || item.assigned !== data.case_count * data.repeats ||
          !Number.isInteger(item.first_passed) || item.first_passed < 0 ||
          states.some((key) => !Number.isInteger(item[key]) || item[key] < 0) ||
          states.reduce((sum, key) => sum + item[key], 0) !== item.assigned || item.first_passed > item.passed ||
          !number(item.attempt_seconds) || item.attempt_seconds <= 0 ||
          !number(item.mean_attempt_seconds) || !number(item.effective_passes_per_hour) ||
          !number(item.candidate_call_seconds) || item.candidate_call_seconds < 0 ||
          !number(item.judge_call_seconds) || item.judge_call_seconds < 0 ||
          item.candidate_call_seconds + item.judge_call_seconds > item.attempt_seconds + 0.01 ||
          Math.abs(item.mean_attempt_seconds - item.attempt_seconds / item.assigned) > 0.001 ||
          Math.abs(item.effective_passes_per_hour - item.passed * 3600 / item.attempt_seconds) > 0.001) {
        throw new Error("Invalid candidate aggregate");
      }
      return {
        label: item.label,
        assigned: item.assigned,
        first: item.first_passed / item.assigned * 100,
        final: item.passed / item.assigned * 100,
        firstCount: item.first_passed,
        finalCount: item.passed,
        mean: item.mean_attempt_seconds,
        throughput: item.effective_passes_per_hour,
        total: item.attempt_seconds,
        candidateTime: item.candidate_call_seconds,
        judgeTime: item.judge_call_seconds,
        outcomes: [item.failed, item.unscored, item.errors, item.timeouts],
      };
    });
    if (rows[0].label === rows[1].label) throw new Error("Duplicate candidate label");
    const maximum = Math.max(...rows.map((row) => row.throughput));
    return {
      caseCount: data.case_count,
      repeats: data.repeats,
      totalAttempts: rows.reduce((sum, row) => sum + row.assigned, 0),
      rows,
      maximum,
      ratio: rows[0].throughput > 0 ? rows[1].throughput / rows[0].throughput : null,
    };
  }

  function put(selector, value) {
    document.querySelectorAll(selector).forEach((node) => { node.textContent = String(value); });
  }

  function show(data) {
    const result = derive(data);
    put("[data-case-count]", result.caseCount);
    put("[data-repeats]", result.repeats);
    put("[data-attempts]", result.totalAttempts);
    put("[data-assigned]", result.rows[0].assigned);
    put("[data-ratio]", result.ratio === null ? "不可计算" : result.ratio.toFixed(2) + "×");
    result.rows.forEach((row, index) => {
      put(`[data-name="${index}"]`, row.label);
      put(`[data-first="${index}"]`, row.first.toFixed(1) + "%");
      put(`[data-final="${index}"]`, row.final.toFixed(1) + "%");
      put(`[data-first-count="${index}"]`, `${row.firstCount} / ${row.assigned}`);
      put(`[data-final-count="${index}"]`, `${row.finalCount} / ${row.assigned}`);
      put(`[data-mean="${index}"]`, row.mean.toFixed(2));
      put(`[data-throughput="${index}"]`, row.throughput.toFixed(2));
      put(`[data-total="${index}"]`, row.total.toFixed(2));
      put(`[data-candidate-time="${index}"]`, row.candidateTime.toFixed(2));
      put(`[data-judge-time="${index}"]`, row.judgeTime.toFixed(2));
      put(`[data-outcomes="${index}"]`, row.outcomes.join(" / "));
      const bar = document.querySelector(`[data-bar="${index}"]`);
      if (bar) bar.style.width = (result.maximum > 0 ? row.throughput / result.maximum * 100 : 0) + "%";
    });
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { derive };
  if (typeof document !== "undefined") {
    fetch(SOURCE, { cache: "no-cache" })
      .then((response) => { if (!response.ok) throw new Error("Aggregate unavailable"); return response.json(); })
      .then(show)
      .catch(() => { document.getElementById("data-error").hidden = false; })
      .finally(() => { document.querySelectorAll("[data-data-region]").forEach((node) => node.setAttribute("aria-busy", "false")); });
  }
})();
