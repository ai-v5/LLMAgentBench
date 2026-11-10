const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { derive } = require('../site/app.js');

const root = path.resolve(__dirname, '..');
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
const publicData = read('results/engineering-public-r3/summary.json');
const overallData = read('results/engineering-overall-ale-r1/terra-dsh-summary.json');
const usage = read('results/engineering-public-r3/token-usage.json');
const newPublicData = read('results/engineering-public-luna-sol-r1/summary.json');
const newOverallData = read('results/engineering-overall-ale-r1/sol-luna-summary.json');
const newUsage = read('results/engineering-public-luna-sol-r1/token-usage.json');
const newComparison = read('results/engineering-public-luna-sol-r1/comparison.json');
const revision = read('results/engineering-overall-case-retest-r1/provenance.json');
const overallProvenance = read('results/engineering-overall-ale-r1/provenance.json');
const kimiPublicData = read('results/engineering-kimi-public-r1/summary.json');
const kimiOverallData = read('results/engineering-kimi-overall-r1/summary.json');
const kimiUsage = read('results/engineering-kimi-public-r1/token-usage.json');
const kimiProvenance = read('results/engineering-kimi-overall-r1/provenance.json');
const effortEfforts = ['low', 'high', 'xhigh', 'max'];
const effortData = Object.fromEntries(effortEfforts.map((effort) => [effort, {
  public: read(`results/engineering-1017-efforts/public-${effort}.json`),
  overall: read(`results/engineering-1017-efforts/overall-${effort}.json`),
  tokens: read(`results/engineering-1017-efforts/tokens-${effort}.json`),
}]));
const effortRevision = read('results/engineering-1017-efforts/revision.json');
const effortProvenance = read('results/engineering-1017-efforts/provenance.json');
const terra = Object.fromEntries(['max', 'high', 'low'].map((effort) => [effort, {
  summary: read(`results/terra-20261110-standard/${effort}/summary.json`),
  tokens: read(`results/terra-20261110-standard/${effort}/token-usage.json`),
  provenance: read(`results/terra-20261110-standard/${effort}/provenance.json`),
  overall: read(`results/terra-20261110-standard/${effort}/overall.json`),
  overallProvenance: read(`results/terra-20261110-standard/${effort}/overall-provenance.json`),
}]));
for (const [effort, entry] of Object.entries(terra)) {
  const row = derive(entry.summary, entry.overall, entry.tokens).rows[0];
  assert.equal(entry.summary.pack_version, '20261110');
  assert.equal(entry.summary.case_count, 13);
  assert.equal(entry.summary.repeats, 2);
  assert.equal(entry.provenance.source_receipts_verified, true);
  assert.equal(entry.provenance.visibility, 'public');
  assert.equal(entry.provenance.synthetic, true);
  assert.equal(entry.provenance.requested_model, 'gpt-6.1-terra');
  assert.equal(entry.provenance.reasoning_effort, effort);
  assert.equal(entry.provenance.mixed_conditions, effort === 'max');
  assert.equal(entry.provenance.sources.reduce((sum, source) => sum + source.selected_cases, 0), 13);
  assert.deepEqual(entry.tokens.source_receipt_sha256.slice().sort(),
    entry.provenance.sources.map(source => source.receipt_sha256).sort());
  assert.equal(entry.overall.case_count, 29);
  assert.equal(entry.overall.pack_version, entry.summary.pack_version);
  assert.equal(entry.overall.candidates[0].assigned, 58);
  assert.equal(entry.overallProvenance.authorized_private_overall, true);
  assert.equal(entry.overallProvenance.private_details_exported, false);
  assert.equal(row.overallFirst, entry.overall.candidates[0].first_passed / 58 * 100);
}
assert.equal(new Set(Object.values(terra).map(entry => entry.provenance.target_pack_sha256)).size, 1);
const lunaMax = {
  summary: read('results/luna-20261110-standard/max/summary.json'),
  tokens: read('results/luna-20261110-standard/max/token-usage.json'),
  provenance: read('results/luna-20261110-standard/max/provenance.json'),
  overall: read('results/luna-20261110-standard/max/overall.json'),
  overallProvenance: read('results/luna-20261110-standard/max/overall-provenance.json'),
};
assert.equal(lunaMax.summary.case_count, 13);
assert.equal(lunaMax.summary.repeats, 2);
assert.equal(lunaMax.overall.case_count, 29);
assert.equal(lunaMax.overall.pack_version, lunaMax.summary.pack_version);
assert.equal(lunaMax.overall.candidates[0].assigned, 58);
assert.equal(lunaMax.provenance.requested_model, 'gpt-6-luna');
assert.equal(lunaMax.provenance.reasoning_effort, 'max');
assert.equal(lunaMax.provenance.mixed_conditions, true);
assert.equal(lunaMax.provenance.source_receipts_verified, true);
assert.deepEqual(lunaMax.tokens.source_receipt_sha256.slice().sort(),
  lunaMax.provenance.sources.map(source => source.receipt_sha256).sort());
assert.equal(lunaMax.overallProvenance.authorized_private_overall, true);
assert.equal(lunaMax.overallProvenance.private_details_exported, false);
assert.equal(derive(lunaMax.summary, lunaMax.overall, lunaMax.tokens).rows[0].overallFirst,
  lunaMax.overall.candidates[0].first_passed / 58 * 100);
const lunaHigh = {
  summary: read('results/luna-20261110-standard/high/summary.json'),
  tokens: read('results/luna-20261110-standard/high/token-usage.json'),
  provenance: read('results/luna-20261110-standard/high/provenance.json'),
  overall: read('results/luna-20261110-standard/high/overall.json'),
  overallProvenance: read('results/luna-20261110-standard/high/overall-provenance.json'),
};
assert.equal(lunaHigh.summary.case_count, 13);
assert.equal(lunaHigh.summary.repeats, 2);
assert.equal(lunaHigh.overall.case_count, 29);
assert.equal(lunaHigh.overall.pack_version, lunaHigh.summary.pack_version);
assert.equal(lunaHigh.overall.candidates[0].assigned, 58);
assert.equal(lunaHigh.provenance.requested_model, 'gpt-6-luna');
assert.equal(lunaHigh.provenance.reasoning_effort, 'high');
assert.equal(lunaHigh.provenance.mixed_conditions, false);
assert.equal(lunaHigh.provenance.source_receipts_verified, true);
assert.deepEqual(lunaHigh.tokens.source_receipt_sha256.slice().sort(),
  lunaHigh.provenance.sources.map(source => source.receipt_sha256).sort());
assert.equal(lunaHigh.overallProvenance.authorized_private_overall, true);
assert.equal(lunaHigh.overallProvenance.private_details_exported, false);
assert.equal(derive(lunaHigh.summary, lunaHigh.overall, lunaHigh.tokens).rows[0].overallFirst,
  lunaHigh.overall.candidates[0].first_passed / 58 * 100);
const lunaLow = {
  summary: read('results/luna-20261110-standard/low/summary.json'),
  tokens: read('results/luna-20261110-standard/low/token-usage.json'),
  provenance: read('results/luna-20261110-standard/low/provenance.json'),
  overall: read('results/luna-20261110-standard/low/overall.json'),
  overallProvenance: read('results/luna-20261110-standard/low/overall-provenance.json'),
};
assert.equal(lunaLow.summary.case_count, 13);
assert.equal(lunaLow.summary.repeats, 2);
assert.equal(lunaLow.overall.case_count, 29);
assert.equal(lunaLow.overall.pack_version, lunaLow.summary.pack_version);
assert.equal(lunaLow.overall.candidates[0].assigned, 58);
assert.equal(lunaLow.provenance.requested_model, 'gpt-6-luna');
assert.equal(lunaLow.provenance.reasoning_effort, 'low');
assert.equal(lunaLow.provenance.mixed_conditions, false);
assert.equal(lunaLow.provenance.source_receipts_verified, true);
assert.deepEqual(lunaLow.tokens.source_receipt_sha256.slice().sort(),
  lunaLow.provenance.sources.map(source => source.receipt_sha256).sort());
assert.equal(lunaLow.overallProvenance.authorized_private_overall, true);
assert.equal(lunaLow.overallProvenance.private_details_exported, false);
assert.equal(derive(lunaLow.summary, lunaLow.overall, lunaLow.tokens).rows[0].overallFirst,
  lunaLow.overall.candidates[0].first_passed / 58 * 100);
for (const summary of [overallData, newOverallData]) {
  assert.deepEqual(Object.keys(summary).sort(), ['candidates', 'case_count', 'denominator', 'schema_version']);
  for (const row of summary.candidates) {
    assert.deepEqual(Object.keys(row).sort(), [
      'assigned', 'attempt_seconds', 'candidate_call_seconds', 'effective_passes_per_hour', 'errors',
      'evidence', 'failed', 'first_passed', 'judge_call_seconds', 'label', 'mean_attempt_seconds',
      'mean_pass_seconds', 'passed', 'timeouts', 'unscored',
    ].sort(), 'Only aggregate fields may enter the public result');
  }
}
assert.deepEqual(Object.keys(overallProvenance).sort(), [
  'assigned_attempts_verified', 'authorized_private_overall', 'denominator', 'private_details_exported',
  'requested_models', 'schema_version',
].sort());
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
assert.doesNotMatch(html, /Terra 20261110|Luna 20261110/, 'The homepage should not display dated report headings');
assert.doesNotMatch(html, /<strong>(?:结果边界|怎么看|输出速度)：<\/strong>/, 'The homepage should not display these explanatory notes');
const table = html.match(/<table class="results-table">([\s\S]*?)<\/table>/);
assert.ok(table, 'The results must remain a semantic table');
assert.equal((html.match(/<table\b/g) || []).length, 1);
assert.equal((table[1].match(/scope="col"/g) || []).length, 4);
assert.match(table[1], /data-sort-key="tokens">输出速度/);
assert.equal((table[1].match(/data-result-row=/g) || []).length, 12);
assert.doesNotMatch(table[1], /data-result-row="(?:0|2)"/);
assert.match(table[1], /data-result-row="8"[^>]*>[\s\S]*?含历史样本/);
for (const key of ['label', 'publicFirst', 'overallFirst', 'tokens']) {
  assert.match(table[1], new RegExp('<button[^>]*type="button"[^>]*data-sort-key="' + key + '"'));
}
for (const field of ['data-public-first', 'data-public-final', 'data-all-first', 'data-all-final', 'data-token-rate']) {
  assert.equal((table[1].match(new RegExp(field + '=', 'g')) || []).length, 12, field);
}
const result = derive(publicData, overallData, usage);
const newResult = derive(newPublicData, newOverallData, newUsage);
const kimiResult = derive(kimiPublicData, kimiOverallData, kimiUsage);
assert.deepEqual(kimiResult.rows.map(row => row.label), ['Kimi K3.1 Pro']);
assert.deepEqual(newResult.rows.map(row => row.label), ['Codex GPT-6.1 Sol', 'Codex GPT-6 Luna']);
assert.equal(newComparison.same_assignment_order, true);
assert.equal(newComparison.same_judge_executable, false);
for (let i = 0; i < result.rows.length; i++) {
  const publicRow = publicData.candidates[i];
  const total = overallData.candidates.find(row => row.label === publicRow.label);
  const tokenRow = usage.candidates.find(row => row.label === publicRow.label);
  assert.equal(result.rows[i].publicFirst, publicRow.first_passed / publicRow.assigned * 100);
  assert.equal(result.rows[i].publicFinal, publicRow.passed / publicRow.assigned * 100);
  assert.equal(result.rows[i].overallFirst, total.first_passed / total.assigned * 100);
  assert.equal(result.rows[i].overallFinal, total.passed / total.assigned * 100);
  assert.equal(result.rows[i].tokens.rate, tokenRow.output_tokens / tokenRow.candidate_call_seconds);
}
const invalid = structuredClone(publicData);
invalid.candidates[0].failed += 1;
assert.throws(() => derive(invalid, overallData, usage), /Invalid candidate summary/);
const wrongRate = structuredClone(overallData);
wrongRate.candidates[0].effective_passes_per_hour += 1;
assert.throws(() => derive(publicData, wrongRate, usage), /Invalid candidate summary/);
const wrongDenominator = structuredClone(overallData);
wrongDenominator.denominator = 'unknown';
assert.throws(() => derive(publicData, wrongDenominator, usage), /Invalid summary/);
const wrongAssignment = structuredClone(overallData);
wrongAssignment.candidates[1].assigned += 1;
wrongAssignment.candidates[1].unscored += 1;
wrongAssignment.candidates[1].mean_attempt_seconds = wrongAssignment.candidates[1].attempt_seconds / wrongAssignment.candidates[1].assigned;
assert.throws(() => derive(publicData, wrongAssignment, usage), /Inconsistent assignments/);
const fixture = structuredClone(publicData);
fixture.candidates[0].evidence = 'FIXTURE_SMOKE';
assert.throws(() => derive(fixture, overallData, usage), /Invalid candidate summary/);
const incompatible = structuredClone(overallData);
incompatible.candidates[0].label = 'Other';
assert.throws(() => derive(publicData, incompatible, usage), /Incompatible candidate summaries/);
const wrongScope = structuredClone(usage);
wrongScope.case_count += 1;
assert.throws(() => derive(publicData, overallData, wrongScope), /Invalid public token aggregate/);
const wrongDuration = structuredClone(usage);
wrongDuration.candidates[0].candidate_call_seconds += 1;
assert.throws(() => derive(publicData, overallData, wrongDuration), /Invalid candidate token aggregate/);
const partial = structuredClone(usage);
partial.candidates[0].usage_calls -= 1;
assert.throws(() => derive(publicData, overallData, partial), /Invalid candidate token aggregate/);
partial.candidates[0].output_tokens = null;
assert.equal(derive(publicData, overallData, partial).rows[0].tokens, null);
assert.equal(derive(publicData, overallData, null).rows[0].tokens, null);

// Synthetic second batch exercises rendering without inventing model results in an artifact.
const secondPublic = structuredClone(publicData);
const secondOverall = structuredClone(overallData);
const secondUsage = structuredClone(usage);
const secondLabels = ['Codex GPT-6.1 Sol', 'Codex GPT-6 Luna'];
for (const source of [secondPublic, secondOverall, secondUsage]) {
  source.candidates.forEach((row, index) => { row.label = secondLabels[index]; });
}
secondUsage.candidates[0].requested_model = 'gpt-6.1-sol';
secondUsage.candidates[1].requested_model = 'gpt-6-luna';

const publicOnlyData = Object.fromEntries(['max', 'high', 'low'].map((effort) => {
  const summary = structuredClone(publicData);
  const tokens = structuredClone(usage);
  const label = `Codex GPT-6.1 Terra ${effort}`;
  summary.candidates = [summary.candidates[0]];
  summary.candidates[0].label = label;
  summary.pack_version = '20261110';
  tokens.candidates = [tokens.candidates[0]];
  tokens.candidates[0].label = label;
  tokens.candidates[0].requested_model = 'gpt-6.1-terra';
  tokens.candidates[0].reasoning_effort = effort;
  tokens.source_receipt_sha256 = [tokens.source_receipt_sha256[0]];
  const provenance = { schema_version: 1, visibility: 'public', synthetic: true, source_receipts_verified: true,
    case_count: summary.case_count, repeats: summary.repeats, pack_version: summary.pack_version,
    requested_model: 'gpt-6.1-terra', reasoning_effort: effort, mixed_conditions: effort === 'max',
    target_pack_sha256: 'a'.repeat(64), sources: [{ selected_cases: summary.case_count,
      receipt_sha256: tokens.source_receipt_sha256[0] }] };
  const overall = structuredClone(summary);
  overall.schema_version = 2;
  overall.denominator = 'assigned_attempts';
  delete overall.repeats;
  overall.case_count += 1;
  const total = overall.candidates[0];
  total.assigned += 2;
  total.first_passed += 1;
  total.passed += 2;
  total.attempt_seconds += 5;
  total.candidate_call_seconds += 2;
  total.mean_attempt_seconds = total.attempt_seconds / total.assigned;
  total.effective_passes_per_hour = total.passed * 3600 / total.attempt_seconds;
  const overallProvenance = { schema_version: 1, authorized_private_overall: true, private_details_exported: false,
    assigned_attempts_verified: true, denominator: 'assigned_attempts', requested_models: ['gpt-6.1-terra'] };
  return [effort, { summary, tokens, provenance, overall, overallProvenance }];
}));
const lunaSynthetic = Object.fromEntries(['max', 'high', 'low'].map((effort) => {
  const entry = structuredClone(publicOnlyData[effort]);
  const label = `Codex GPT-6 Luna ${effort}`;
  for (const data of [entry.summary, entry.overall, entry.tokens]) data.candidates[0].label = label;
  entry.tokens.candidates[0].requested_model = 'gpt-6-luna';
  entry.provenance.requested_model = 'gpt-6-luna';
  entry.overallProvenance.requested_models = ['gpt-6-luna'];
  return [effort, entry];
}));

async function checkLoading(secondResponses, beforeLoad, revisionResponse, overallProvenanceResponse, publicOnlyOverride, lunaOverride) {
  const alerts = { 'data-error': { hidden: true }, 'token-error': { hidden: true } };
  const region = { busy: true, setAttribute(name, value) { if (name === 'aria-busy') this.busy = value !== 'false'; } };
  const nodes = new Map();
  const rowIds = [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13];
  const rows = [];
  for (const index of rowIds) {
    rows[index] = { hidden: true, getAttribute: (name) => name === 'data-result-row' ? String(index) : null };
  }
  const order = rows.filter(Boolean);
  const body = {
    querySelectorAll: () => order.slice(),
    appendChild(row) { order.splice(order.indexOf(row), 1); order.push(row); },
  };
  const buttons = Object.fromEntries(['label', 'publicFirst', 'overallFirst', 'tokens'].map((key) => {
    const header = {
      attributes: {},
      setAttribute(name, value) { this.attributes[name] = value; },
      removeAttribute(name) { delete this.attributes[name]; },
    };
    return [key, {
      dataset: { sortKey: key }, header,
      closest: () => header,
      addEventListener(name, handler) { if (name === 'click') this.click = handler; },
    }];
  }));
  const document = {
    getElementById: (id) => alerts[id],
    querySelector: (selector) => {
      if (selector === '.results-table tbody') return body;
      const match = selector.match(/^\[data-result-row="(\d+)"\]$/);
      return match ? rows[Number(match[1])] : null;
    },
    querySelectorAll: (selector) => {
      if (selector === '[data-data-region]') return [region];
      if (selector === '[data-sort-key]') return Object.values(buttons);
      if (!nodes.has(selector)) nodes.set(selector, { textContent: '' });
      return [nodes.get(selector)];
    },
  };
  const code = fs.readFileSync(path.join(root, 'site/app.js'), 'utf8');
  const fetch = async (url) => {
    if (url.includes('terra-20261110-standard/')) {
      const match = url.match(/terra-20261110-standard\/(max|high|low)\/(summary|token-usage|provenance|overall|overall-provenance)\.json/);
      const entry = (publicOnlyOverride || publicOnlyData)[match[1]];
      const key = match[2] === 'token-usage' ? 'tokens' : match[2] === 'overall-provenance' ? 'overallProvenance' : match[2];
      return entry[key] && entry[key].ok === false ? entry[key] : ok(entry[key]);
    }
    if (url.includes('luna-20261110-standard/')) {
      const match = url.match(/luna-20261110-standard\/(max|high|low)\/(summary|token-usage|provenance|overall|overall-provenance)\.json/);
      const key = match[2] === 'token-usage' ? 'tokens' : match[2] === 'overall-provenance' ? 'overallProvenance' : match[2];
      return ok((lunaOverride || lunaSynthetic)[match[1]][key]);
    }
    if (url.includes('engineering-1017-efforts/revision.json')) return ok(effortRevision);
    if (url.includes('engineering-1017-efforts/provenance.json')) return ok(effortProvenance);
    if (url.includes('engineering-1017-efforts/')) {
      const match = url.match(/engineering-1017-efforts\/(public|overall|tokens)-(\w+)\.json/);
      return ok(effortData[match[2]][match[1]]);
    }
    if (url.includes('engineering-overall-case-retest-r1/provenance.json')) return revisionResponse || ok(revision);
    if (url.includes('engineering-overall-ale-r1/provenance.json')) return overallProvenanceResponse || ok(overallProvenance);
    if (url.includes('engineering-kimi-overall-r1/provenance.json')) return ok(kimiProvenance);
    if (url.includes('engineering-kimi-public-r1/summary.json')) return ok(kimiPublicData);
    if (url.includes('engineering-kimi-overall-r1/summary.json')) return ok(kimiOverallData);
    if (url.includes('engineering-kimi-public-r1/token-usage.json')) return ok(kimiUsage);
    if (url.includes('sol-luna-summary.json')) return secondResponses.overall;
    if (url.includes('luna-sol-r1')) {
      if (url.includes('comparison.json')) return secondResponses.comparison;
      return url.includes('token-usage') ? secondResponses.tokens : url.includes('engineering-public') ? secondResponses.public : secondResponses.overall;
    }
    throw new Error('Unexpected fetch: ' + url);
  };
  vm.runInNewContext(code, { document, fetch });
  if (beforeLoad) beforeLoad(buttons);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(region.busy, false);
  return { alerts, nodes, rows, order, buttons };
}

const ok = (value) => ({ ok: true, json: async () => value });
(async () => {
  const comparison = { schema_version: 1, same_pack_order: true, same_assignment_order: true, same_engine: true, same_driver: true,
    same_budget: true, same_judge_configuration: true, same_judge_executable: false,
    requested_models: ['gpt-6-luna', 'gpt-6.1-sol'] };
  const second = { public: ok(secondPublic), overall: ok(secondOverall), tokens: ok(secondUsage), comparison: ok(comparison) };
  let page = await checkLoading(second, undefined, ok({ ...revision, case_revision_verified: false }));
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[1].hidden, true);
  assert.equal(page.rows[3].hidden, false);
  page = await checkLoading(second, undefined, undefined, ok({ ...overallProvenance, private_details_exported: true }));
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[1].hidden, true);
  assert.equal(page.rows[3].hidden, false);
  page = await checkLoading({ ...second, public: { ok: false } });
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[1].hidden, true);
  assert.equal(page.rows[8].hidden, false);
  page = await checkLoading({ ...second, tokens: { ok: false } });
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, false);
  assert.equal(page.nodes.get('[data-public-first="1"]').textContent, '100.0%');
  assert.equal(page.nodes.get('[data-token-rate="1"]').textContent, '未记录');
  const wrongSecondScope = structuredClone(secondUsage);
  wrongSecondScope.case_count += 1;
  page = await checkLoading({ ...second, tokens: ok(wrongSecondScope) });
  assert.equal(page.alerts['token-error'].hidden, false);
  assert.equal(page.nodes.get('[data-token-rate="1"]').textContent, '未记录');
  page = await checkLoading(second);
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, true);
  assert.equal(page.nodes.get('[data-token-rate="1"]').textContent, (12448 / 1357.219).toFixed(2));
  assert.equal(page.nodes.get('[data-pack="1"]').textContent, '题库 未标注');
  assert.equal(page.nodes.get('[data-all-first="1"]').textContent, result.rows[0].overallFirst.toFixed(1) + '%');
  assert.equal(page.nodes.get('[data-name="1"]').textContent, 'Codex GPT-6.1 Sol');
  const currentTotal = publicOnlyData.max.overall.candidates[0];
  assert.equal(page.nodes.get('[data-all-first="8"]').textContent, (currentTotal.first_passed / currentTotal.assigned * 100).toFixed(1) + '%');
  assert.equal(page.nodes.get('[data-name="11"]').textContent, 'Codex GPT-6 Luna max');
  assert.equal(page.rows.every(row => !row.hidden), true);
  const labels = page.order.map(row => page.nodes.get('[data-name="' + row.getAttribute('data-result-row') + '"]').textContent);
  assert.equal(labels.includes('Codex GPT-6.1 Terra'), false);
  assert.equal(labels.includes('Codex GPT-6 Luna'), false);
  for (const effort of ['max', 'high', 'low']) {
    assert.ok(labels.includes(`Codex GPT-6.1 Terra ${effort}`));
    assert.ok(labels.includes(`Codex GPT-6 Luna ${effort}`));
  }
  const wrongLunaModel = structuredClone(lunaSynthetic);
  wrongLunaModel.max.provenance.requested_model = 'gpt-6.1-terra';
  page = await checkLoading(second, null, null, null, null, wrongLunaModel);
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[11].hidden, true);
  const badPublicProvenance = structuredClone(publicOnlyData);
  badPublicProvenance.max.provenance.source_receipts_verified = false;
  page = await checkLoading(second, null, null, null, badPublicProvenance);
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[8].hidden, true);
  const wrongCurrentVersion = structuredClone(publicOnlyData);
  wrongCurrentVersion.max.overall.pack_version = '20261110-v2';
  page = await checkLoading(second, null, null, null, wrongCurrentVersion);
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[8].hidden, true);
  const badCurrentOverallProvenance = structuredClone(publicOnlyData);
  badCurrentOverallProvenance.max.overallProvenance.private_details_exported = true;
  page = await checkLoading(second, null, null, null, badCurrentOverallProvenance);
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[8].hidden, true);
  const mismatchedPublicTokens = structuredClone(publicOnlyData);
  mismatchedPublicTokens.max.tokens.source_receipt_sha256 = ['b'.repeat(64)];
  page = await checkLoading(second, null, null, null, mismatchedPublicTokens);
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, false);
  assert.equal(page.rows[8].hidden, false);
  assert.equal(page.nodes.get('[data-token-rate="8"]').textContent, '未记录');
  page = await checkLoading({ ...second, comparison: ok({ ...comparison, same_pack_order: false }) });
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[1].hidden, true);
  const realSecond = { public: ok(newPublicData), overall: ok(newOverallData), tokens: ok(newUsage), comparison: ok(newComparison) };
  page = await checkLoading(realSecond);
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, true);
  assert.equal(page.rows.every(row => !row.hidden), true);
  assert.equal(page.nodes.get('[data-public-first="1"]').textContent, newResult.rows[0].publicFirst.toFixed(1) + '%');
  assert.equal(page.nodes.get('[data-token-rate="1"]').textContent, newResult.rows[0].tokens.rate.toFixed(2));
  const swapped = structuredClone(secondUsage);
  swapped.candidates[0].requested_model = 'gpt-6-luna';
  page = await checkLoading({ ...second, tokens: ok(swapped) });
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[1].hidden, true);
  const withError = structuredClone(secondPublic);
  const overallWithError = structuredClone(secondOverall);
  for (const source of [withError, overallWithError]) {
    const row = source.candidates[0];
    row.passed -= 1;
    row.first_passed = Math.min(row.first_passed, row.passed);
    row.errors += 1;
    row.effective_passes_per_hour = row.passed * 3600 / row.attempt_seconds;
  }
  page = await checkLoading({ ...second, public: ok(withError), overall: ok(overallWithError) });
  const issueRow = overallWithError.candidates[0];
  assert.ok(page.nodes.get('[data-all-final="1"]').textContent.includes(
    `未评分/错误/超时 ${issueRow.unscored}/${issueRow.errors}/${issueRow.timeouts}`));

  const indices = (value) => value.order.map(row => Number(row.getAttribute('data-result-row')));
  const effortResults = effortEfforts.map((effort) => derive(effortData[effort].public, effortData[effort].overall, effortData[effort].tokens));
  const publicOnlyRows = ['max', 'high', 'low'].map((effort) => derive(publicOnlyData[effort].summary, publicOnlyData[effort].overall, publicOnlyData[effort].tokens).rows[0]);
  const lunaRows = ['max', 'high', 'low'].map((effort) => derive(lunaSynthetic[effort].summary, lunaSynthetic[effort].overall, lunaSynthetic[effort].tokens).rows[0]);
  const allRows = { 1: newResult.rows[0], 3: kimiResult.rows[0] };
  effortResults.forEach((entry, index) => { allRows[4 + index] = entry.rows[0]; });
  publicOnlyRows.forEach((entry, index) => { allRows[8 + index] = entry; });
  lunaRows.forEach((entry, index) => { allRows[11 + index] = entry; });
  const expectedOrder = (valueOf, direction) => {
    const items = Object.keys(allRows).map(Number).map(index => ({ index, value: valueOf(index) }));
    items.sort((left, right) => {
      const a = left.value, b = right.value;
      if (a == null || b == null) return a == null && b == null ? left.index - right.index : a == null ? 1 : -1;
      const comparison = typeof a === 'string' ? a.localeCompare(b, 'en', { numeric: true, sensitivity: 'base' }) : a - b;
      return (direction === 'ascending' ? comparison : -comparison) || left.index - right.index;
    });
    return items.map((item) => item.index);
  };
  const expectedOverall = (direction) => expectedOrder((i) => allRows[i].overallFirst, direction === 1 ? 'ascending' : 'descending');
  page = await checkLoading(realSecond);
  assert.deepEqual(indices(page), expectedOverall(-1), 'Overall first-pass score defaults to descending');
  assert.equal(page.buttons.overallFirst.header.attributes['aria-sort'], 'descending');
  page.buttons.overallFirst.click();
  assert.deepEqual(indices(page), expectedOverall(1), 'The first click reverses the default order');
  assert.equal(page.buttons.overallFirst.header.attributes['aria-sort'], 'ascending');
  page = await checkLoading(realSecond, buttons => buttons.overallFirst.click());
  assert.deepEqual(indices(page), expectedOverall(1), 'An early click overrides the default while data loads');
  page = await checkLoading(realSecond, buttons => buttons.tokens.click());
  assert.deepEqual(indices(page), expectedOrder((i) => allRows[i].tokens ? allRows[i].tokens.rate : null, 'descending'), 'A sort selected before loading must include all batches');
  assert.equal(page.buttons.tokens.header.attributes['aria-sort'], 'descending');
  page.buttons.tokens.click();
  assert.deepEqual(indices(page), expectedOrder((i) => allRows[i].tokens ? allRows[i].tokens.rate : null, 'ascending'), 'Token rates sort numerically in ascending order');
  assert.equal(page.buttons.tokens.header.attributes['aria-sort'], 'ascending');
  page.buttons.publicFirst.click();
  assert.deepEqual(indices(page), expectedOrder((i) => allRows[i].publicFirst, 'descending'), 'Public scores default to descending with stable ties');
  assert.equal(page.buttons.tokens.header.attributes['aria-sort'], undefined);
  assert.equal(page.buttons.publicFirst.header.attributes['aria-sort'], 'descending');
  page.buttons.publicFirst.click();
  assert.deepEqual(indices(page), expectedOrder((i) => allRows[i].publicFirst, 'ascending'));
  page.buttons.overallFirst.click();
  assert.deepEqual(indices(page), expectedOverall(-1), 'Overall scores use the unrounded first-pass values');
  page.buttons.overallFirst.click();
  assert.deepEqual(indices(page), expectedOverall(1));
  page.buttons.label.click();
  assert.deepEqual(indices(page), expectedOrder((i) => allRows[i].label, 'ascending'), 'Names default to ascending');
  page.buttons.label.click();
  assert.deepEqual(indices(page), expectedOrder((i) => allRows[i].label, 'descending'));

  page = await checkLoading({ ...realSecond, tokens: { ok: false } });
  page.buttons.tokens.click();
  assert.deepEqual(indices(page), expectedOrder((i) => i === 1 ? null : (allRows[i].tokens ? allRows[i].tokens.rate : null), 'descending'), 'Missing token rates stay last when descending');
  page.buttons.tokens.click();
  assert.deepEqual(indices(page), expectedOrder((i) => i === 1 ? null : (allRows[i].tokens ? allRows[i].tokens.rate : null), 'ascending'), 'Missing token rates stay last when ascending');
  page = await checkLoading({ ...realSecond, public: { ok: false } });
  page.buttons.publicFirst.click();
  assert.deepEqual(indices(page), expectedOrder((i) => i === 1 ? null : allRows[i].publicFirst, 'descending'), 'Hidden rows stay after loaded results');
  assert.equal(page.rows[1].hidden, true);
  console.log('Site aggregate, sorting, and failure handling: passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
