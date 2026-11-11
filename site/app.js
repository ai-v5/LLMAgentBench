/* The overall source contains only authorized totals; token data is public synthetic only. */
(function () {
  "use strict";
  const BATCHES = [
    ...[["max", 0], ["low", 14]].map(([effort, offset]) => ({
      public: `results/sol-20261111-standard/${effort}/summary.json`,
      overall: `results/sol-20261111-standard/${effort}/overall.json`,
      overall_provenance: `results/sol-20261111-standard/${effort}/overall-provenance.json`,
      tokens: `results/sol-20261111-standard/${effort}/token-usage.json`,
      public_provenance: `results/sol-20261111-standard/${effort}/provenance.json`, offset,
      effort, model: "gpt-6.1-sol", require_reverified: true, selection_granularity: "case_repeat",
      models: { [`Codex GPT-6.1 Sol ${effort}`]: "gpt-6.1-sol" },
    })),
    { public: "results/engineering-kimi-public-r1/summary.json", overall: "results/engineering-kimi-overall-r1/summary.json",
      tokens: "results/engineering-kimi-public-r1/token-usage.json",
      revision: "results/engineering-kimi-overall-r1/provenance.json",
      overall_provenance: "results/engineering-kimi-overall-r1/provenance.json", offset: 1,
      revision_models: ["k3d1-agent"], overall_models: ["k3d1-agent"],
      models: { "Kimi K3.1 Pro": "k3d1-agent" } },
    ...['max', 'high', 'low'].map((effort, index) => ({
      public: `results/terra-20261111-standard/${effort}/summary.json`,
      overall: `results/terra-20261111-standard/${effort}/overall.json`,
      overall_provenance: `results/terra-20261111-standard/${effort}/overall-provenance.json`,
      tokens: `results/terra-20261111-standard/${effort}/token-usage.json`,
      public_provenance: `results/terra-20261111-standard/${effort}/provenance.json`, offset: 2 + index,
      effort, model: "gpt-6.1-terra", models: { [`Codex GPT-6.1 Terra ${effort}`]: "gpt-6.1-terra" },
    })),
    ...['max', 'high', 'low'].map((effort, index) => ({
      public: `results/luna-20261111-standard/${effort}/summary.json`,
      overall: `results/luna-20261111-standard/${effort}/overall.json`,
      overall_provenance: `results/luna-20261111-standard/${effort}/overall-provenance.json`,
      tokens: `results/luna-20261111-standard/${effort}/token-usage.json`,
      public_provenance: `results/luna-20261111-standard/${effort}/provenance.json`, offset: 5 + index,
      effort, model: "gpt-6-luna", models: { [`Codex GPT-6 Luna ${effort}`]: "gpt-6-luna" },
    })),
    ...['low', 'high', 'max'].map((effort, index) => ({
      public: `results/exp-20261111/flex/${effort}/summary.json`,
      overall: `results/exp-20261111/flex/${effort}/overall.json`,
      overall_provenance: `results/exp-20261111/flex/${effort}/overall-provenance.json`,
      tokens: `results/exp-20261111/flex/${effort}/token-usage.json`,
      public_provenance: `results/exp-20261111/flex/${effort}/provenance.json`, offset: 8 + index,
      effort, model: "ds-v4.1-flash-1017-flex", models: { [`DSH V4.1 Flash 1017 Flex ${effort}`]: "ds-v4.1-flash-1017-flex" },
    })),
    ...['low', 'high', 'max'].map((effort, index) => ({
      public: `results/exp-20261111/glm/${effort}/summary.json`,
      overall: `results/exp-20261111/glm/${effort}/overall.json`,
      overall_provenance: `results/exp-20261111/glm/${effort}/overall-provenance.json`,
      tokens: `results/exp-20261111/glm/${effort}/token-usage.json`,
      public_provenance: `results/exp-20261111/glm/${effort}/provenance.json`, offset: 11 + index,
      effort, model: "glm5.3", models: { [`GLM 5.3 ${effort}`]: "glm5.3" },
    })),
  ];
  const states = ["passed", "failed", "unscored", "errors", "timeouts"];
  const number = (value) => typeof value === "number" && Number.isFinite(value);
  const count = (value) => Number.isInteger(value) && value >= 0;
  const sortData = new Map();
  let currentSort = { key: "overallFirst", direction: "descending" };

  function validate(summary) {
    if (!summary || ![1, 2].includes(summary.schema_version) || !Number.isInteger(summary.case_count) || summary.case_count < 1 ||
        (summary.schema_version === 1 && (!Number.isInteger(summary.repeats) || summary.repeats < 1)) ||
        (summary.schema_version === 2 && summary.denominator !== "assigned_attempts") ||
        !Array.isArray(summary.candidates) || summary.candidates.length < 1) throw new Error("Invalid summary");
    for (const row of summary.candidates) {
      if (!row || typeof row.label !== "string" || !row.label.trim() || row.evidence !== "MODEL_RUN" ||
          !Number.isInteger(row.assigned) ||
          (summary.schema_version === 1 && row.assigned !== summary.case_count * summary.repeats) ||
          (summary.schema_version === 2 && row.assigned < summary.case_count) ||
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
    if (summary.schema_version === 2 && new Set(summary.candidates.map((row) => row.assigned)).size !== 1) throw new Error("Inconsistent assignments");
  }

  function derive(publicData, overallData, usage) {
    validate(publicData);
    if (overallData) validate(overallData);
    if (overallData && ((overallData.schema_version === 1 && publicData.repeats !== overallData.repeats) || publicData.case_count > overallData.case_count)) {
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
      const total = overallData && overallData.candidates.find((row) => row.label === item.label);
      if (overallData && (!total || item.assigned > total.assigned || item.first_passed > total.first_passed ||
          states.some((key) => item[key] > total[key]))) {
        throw new Error("Incompatible candidate summaries");
      }
      let tokens = null;
      if (usage) {
        const row = usage.candidates.find((entry) => entry.label === item.label);
        if (!row || row.evidence_level !== "MODEL_RUN" || !["codex", "dsh", "kimi"].includes(row.adapter) ||
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
      return { label: item.label, packVersion: publicData.pack_version || (overallData && overallData.pack_version) || null,
        publicFirst: item.first_passed / item.assigned * 100,
        publicFinal: item.passed / item.assigned * 100, overallFirst: total ? total.first_passed / total.assigned * 100 : null,
        overallFinal: total ? total.passed / total.assigned * 100 : null,
        publicIssues: [item.unscored, item.errors, item.timeouts],
        overallIssues: total ? [total.unscored, total.errors, total.timeouts] : null, tokens };
    });
    return { rows };
  }

  function put(selector, value) {
    document.querySelectorAll(selector).forEach((node) => { node.textContent = String(value); });
  }

  function validateRevision(value, expectedModels) {
    const flags = ['historical_receipts_verified', 'retest_receipts_verified', 'case_revision_verified',
      'same_engine', 'same_budget', 'mixed_batches'];
    if (!value || value.schema_version !== 1 || flags.some((key) => value[key] !== true) ||
        typeof value.client_identity_changed !== 'boolean' || !Array.isArray(value.requested_models) ||
        value.requested_models.slice().sort().join(',') !== expectedModels.slice().sort().join(',')) {
      throw new Error('Case revision provenance unavailable');
    }
  }

  function validateOverallProvenance(value, expectedModels) {
    if (!value || value.schema_version !== 1 || value.authorized_private_overall !== true ||
        value.private_details_exported !== false || value.assigned_attempts_verified !== true ||
        value.denominator !== "assigned_attempts" || !Array.isArray(value.requested_models) ||
        value.requested_models.slice().sort().join(",") !== expectedModels.slice().sort().join(",")) {
      throw new Error("Overall provenance unavailable");
    }
  }

  function validatePublicProvenance(value, data, batch) {
    const byAssignment = value && value.selection_granularity === "case_repeat";
    if (!value || value.schema_version !== 1 || value.visibility !== "public" || value.synthetic !== true ||
        value.source_receipts_verified !== true || value.case_count !== data.case_count || value.repeats !== data.repeats ||
        value.pack_version !== data.pack_version || value.requested_model !== batch.model ||
        value.reasoning_effort !== batch.effort || typeof value.mixed_conditions !== "boolean" ||
        (batch.require_reverified && value.source_receipts_reverified_now !== true) ||
        (batch.selection_granularity && value.selection_granularity !== batch.selection_granularity) ||
        (Object.hasOwn(value, "selection_granularity") && !byAssignment) ||
        !/^[a-f0-9]{64}$/.test(value.target_pack_sha256) || !Array.isArray(value.sources) || !value.sources.length ||
        value.sources.some((source) => !Number.isInteger(byAssignment ? source.selected_assignments : source.selected_cases) ||
          (byAssignment ? source.selected_assignments : source.selected_cases) < 1 ||
          !/^[a-f0-9]{64}$/.test(source.receipt_sha256)) ||
        value.sources.reduce((sum, source) => sum + (byAssignment ? source.selected_assignments : source.selected_cases), 0) !==
          data.case_count * (byAssignment ? data.repeats : 1) ||
        new Set(value.sources.map((source) => source.receipt_sha256)).size !== value.sources.length) {
      throw new Error("Public source provenance unavailable");
    }
    if (Object.hasOwn(value, "source_receipts_reverified_now") &&
        (typeof value.source_receipts_reverified_now !== "boolean" ||
         (value.source_receipts_reverified_now === false &&
          (!/^[a-f0-9]{40}$/.test(value.source_publication_commit || "") ||
           typeof value.source_pack_version !== "string" || !value.source_pack_version ||
           typeof value.verification_boundary !== "string" || !value.verification_boundary)))) {
      throw new Error("Public source verification boundary unavailable");
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
      put(attr("data-pack"), "题库 " + (row.packVersion || "未标注"));
      put(attr("data-public-first"), row.publicFirst.toFixed(1) + "%");
      put(attr("data-public-final"), finalText(row.publicFinal, row.publicIssues));
      put(attr("data-all-first"), row.overallFirst === null ? "未公开" : row.overallFirst.toFixed(1) + "%");
      put(attr("data-all-final"), row.overallFinal === null ? "仅展示公开题" : finalText(row.overallFinal, row.overallIssues));
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
    sortButtons.forEach((button) => {
      if (button.dataset.sortKey === currentSort.key) {
        button.closest("th").setAttribute("aria-sort", currentSort.direction);
      }
      button.addEventListener("click", () => {
        const key = button.dataset.sortKey;
        const direction = currentSort.key === key
          ? (currentSort.direction === "ascending" ? "descending" : "ascending")
          : (key === "label" ? "ascending" : "descending");
        currentSort = { key, direction };
        sortButtons.forEach((control) => control.closest("th").removeAttribute("aria-sort"));
        button.closest("th").setAttribute("aria-sort", direction);
        sortRows();
      });
    });
    async function loadBatch(batch) {
      try {
        let publicData, overallData, publicProvenance;
        if (batch.public_provenance) {
          const [summary, provenance, total, totalProvenance] = await Promise.all([
            fetch(batch.public, { cache: "no-cache" }), fetch(batch.public_provenance, { cache: "no-cache" }),
            fetch(batch.overall, { cache: "no-cache" }), fetch(batch.overall_provenance, { cache: "no-cache" }),
          ]);
          if (!summary.ok || !provenance.ok || !total.ok || !totalProvenance.ok) throw new Error("Summary or provenance unavailable");
          publicData = await summary.json();
          publicProvenance = await provenance.json();
          validatePublicProvenance(publicProvenance, publicData, batch);
          overallData = await total.json();
          validateOverallProvenance(await totalProvenance.json(), [batch.model]);
          if (overallData.pack_version !== publicData.pack_version) throw new Error("Overall pack version differs");
        } else {
          const revision = await fetch(batch.revision, { cache: "no-cache" });
          if (!revision.ok) throw new Error("Case revision provenance unavailable");
          validateRevision(await revision.json(), batch.revision_models || ["gpt-6.1-terra", "ds-v4.1-flash-1017", "gpt-6.1-sol", "gpt-6-luna"]);
          const overallProvenance = await fetch(batch.overall_provenance || "results/engineering-overall-ale-r1/provenance.json", { cache: "no-cache" });
          if (!overallProvenance.ok) throw new Error("Overall provenance unavailable");
          validateOverallProvenance(await overallProvenance.json(), batch.overall_models || ["gpt-6.1-terra", "ds-v4.1-flash-1017", "gpt-6.1-sol", "gpt-6-luna"]);
          const responses = await Promise.all([fetch(batch.public, { cache: "no-cache" }), fetch(batch.overall, { cache: "no-cache" })]);
          if (responses.some((response) => !response.ok)) throw new Error("Summary unavailable");
          [publicData, overallData] = await Promise.all(responses.map((response) => response.json()));
        }
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
          if (batch.public_provenance && (usage.candidates.some((row) => row.reasoning_effort !== batch.effort) ||
              !Array.isArray(usage.source_receipt_sha256) ||
              usage.source_receipt_sha256.slice().sort().join(",") !== publicProvenance.sources.map((source) => source.receipt_sha256).sort().join(","))) {
            throw new Error("Token aggregate source identity mismatch");
          }
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
