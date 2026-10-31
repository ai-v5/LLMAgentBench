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
const table = html.match(/<table class="results-table">([\s\S]*?)<\/table>/);
assert.ok(table, 'The results must remain a semantic table');
assert.equal((html.match(/<table\b/g) || []).length, 1);
assert.equal((table[1].match(/scope="col"/g) || []).length, 4);
assert.equal((table[1].match(/data-result-row=/g) || []).length, 4);
for (const key of ['label', 'publicFirst', 'overallFirst', 'tokens']) {
  assert.match(table[1], new RegExp('<button[^>]*type="button"[^>]*data-sort-key="' + key + '"'));
}
for (const field of ['data-public-first', 'data-public-final', 'data-all-first', 'data-all-final', 'data-token-rate']) {
  assert.equal((table[1].match(new RegExp(field + '=', 'g')) || []).length, 4, field);
}
const result = derive(publicData, overallData, usage);
const newResult = derive(newPublicData, newOverallData, newUsage);
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

async function checkLoading(publicResponse, overallResponse, tokenResponse, secondResponses, beforeLoad, revisionResponse, overallProvenanceResponse) {
  const alerts = { 'data-error': { hidden: true }, 'token-error': { hidden: true } };
  const region = { busy: true, setAttribute(name, value) { if (name === 'aria-busy') this.busy = value !== 'false'; } };
  const nodes = new Map();
  const rows = Array.from({ length: 4 }, (_, index) => ({
    hidden: true, getAttribute: (name) => name === 'data-result-row' ? String(index) : null,
  }));
  const order = rows.slice();
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
    if (url.includes('engineering-overall-case-retest-r1/provenance.json')) return revisionResponse || ok(revision);
    if (url.includes('engineering-overall-ale-r1/provenance.json')) return overallProvenanceResponse || ok(overallProvenance);
    if (url.includes('sol-luna-summary.json')) return secondResponses.overall;
    if (url.includes('luna-sol-r1')) {
      if (url.includes('comparison.json')) return secondResponses.comparison;
      return url.includes('token-usage') ? secondResponses.tokens : url.includes('engineering-public') ? secondResponses.public : secondResponses.overall;
    }
    return url.includes('token-usage') ? tokenResponse : url.includes('engineering-public') ? publicResponse : overallResponse;
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
  let page = await checkLoading(ok(publicData), ok(overallData), ok(usage), second, undefined,
    ok({ ...revision, case_revision_verified: false }));
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows.every(row => row.hidden), true);
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), second, undefined, undefined,
    ok({ ...overallProvenance, private_details_exported: true }));
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows.every(row => row.hidden), true);
  page = await checkLoading({ ok: false }, ok(overallData), { ok: false }, second);
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[0].hidden, true);
  assert.equal(page.rows[2].hidden, false);
  page = await checkLoading(ok(publicData), ok(overallData), { ok: false }, second);
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, false);
  assert.equal(page.nodes.get('[data-public-first="0"]').textContent, '100.0%');
  assert.equal(page.nodes.get('[data-token-rate="0"]').textContent, '未记录');
  page = await checkLoading(ok(publicData), ok(overallData), ok(wrongScope), second);
  assert.equal(page.alerts['token-error'].hidden, false);
  assert.equal(page.nodes.get('[data-token-rate="0"]').textContent, '未记录');
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), second);
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, true);
  assert.equal(page.nodes.get('[data-token-rate="0"]').textContent, (12448 / 1357.219).toFixed(2));
  assert.equal(page.nodes.get('[data-all-first="0"]').textContent, result.rows[0].overallFirst.toFixed(1) + '%');
  assert.equal(page.nodes.get('[data-name="2"]').textContent, 'Codex GPT-6.1 Sol');
  assert.equal(page.rows.every(row => !row.hidden), true);
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), { ...second, public: { ok: false } });
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[0].hidden, false);
  assert.equal(page.rows[2].hidden, true);
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), {
    ...second, comparison: ok({ ...comparison, same_pack_order: false }) });
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[2].hidden, true);
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), {
    public: ok(newPublicData), overall: ok(newOverallData), tokens: ok(newUsage), comparison: ok(newComparison) });
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, true);
  assert.equal(page.rows.every(row => !row.hidden), true);
  assert.equal(page.nodes.get('[data-public-first="2"]').textContent, newResult.rows[0].publicFirst.toFixed(1) + '%');
  assert.equal(page.nodes.get('[data-token-rate="3"]').textContent, newResult.rows[1].tokens.rate.toFixed(2));
  const swapped = structuredClone(secondUsage);
  swapped.candidates[0].requested_model = 'gpt-6-luna';
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), { ...second, tokens: ok(swapped) });
  assert.equal(page.alerts['data-error'].hidden, false);
  assert.equal(page.rows[2].hidden, true);
  const withError = structuredClone(secondPublic);
  const overallWithError = structuredClone(secondOverall);
  for (const source of [withError, overallWithError]) {
    const row = source.candidates[1];
    row.passed -= 1;
    row.errors += 1;
    row.effective_passes_per_hour = row.passed * 3600 / row.attempt_seconds;
  }
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), {
    ...second, public: ok(withError), overall: ok(overallWithError) });
  const issueRow = overallWithError.candidates[1];
  assert.ok(page.nodes.get('[data-all-final="3"]').textContent.includes(
    `未评分/错误/超时 ${issueRow.unscored}/${issueRow.errors}/${issueRow.timeouts}`));

  const realSecond = { public: ok(newPublicData), overall: ok(newOverallData), tokens: ok(newUsage), comparison: ok(newComparison) };
  const indices = (value) => value.order.map(row => Number(row.getAttribute('data-result-row')));
  const allRows = [...result.rows, ...newResult.rows];
  const expectedOverall = (direction) => allRows.map((row, index) => ({ value: row.overallFirst, index }))
    .sort((a, b) => direction * (a.value - b.value) || a.index - b.index).map(item => item.index);
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), realSecond);
  assert.deepEqual(indices(page), expectedOverall(-1), 'Overall first-pass score defaults to descending');
  assert.equal(page.buttons.overallFirst.header.attributes['aria-sort'], 'descending');
  page.buttons.overallFirst.click();
  assert.deepEqual(indices(page), expectedOverall(1), 'The first click reverses the default order');
  assert.equal(page.buttons.overallFirst.header.attributes['aria-sort'], 'ascending');
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), realSecond, buttons => buttons.overallFirst.click());
  assert.deepEqual(indices(page), expectedOverall(1), 'An early click overrides the default while data loads');
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage), realSecond, buttons => buttons.tokens.click());
  assert.deepEqual(indices(page), [1, 3, 0, 2], 'A sort selected before loading must include both batches');
  assert.equal(page.buttons.tokens.header.attributes['aria-sort'], 'descending');
  page.buttons.tokens.click();
  assert.deepEqual(indices(page), [2, 0, 3, 1], 'Token rates sort numerically in ascending order');
  assert.equal(page.buttons.tokens.header.attributes['aria-sort'], 'ascending');
  page.buttons.publicFirst.click();
  assert.deepEqual(indices(page), [0, 2, 3, 1], 'Public scores default to descending with stable ties');
  assert.equal(page.buttons.tokens.header.attributes['aria-sort'], undefined);
  assert.equal(page.buttons.publicFirst.header.attributes['aria-sort'], 'descending');
  page.buttons.publicFirst.click();
  assert.deepEqual(indices(page), [1, 0, 2, 3]);
  page.buttons.overallFirst.click();
  assert.deepEqual(indices(page), expectedOverall(-1), 'Overall scores use the unrounded first-pass values');
  page.buttons.overallFirst.click();
  assert.deepEqual(indices(page), expectedOverall(1));
  page.buttons.label.click();
  assert.deepEqual(indices(page), [3, 2, 0, 1], 'Names default to ascending');
  page.buttons.label.click();
  assert.deepEqual(indices(page), [1, 0, 2, 3]);
  assert.equal(page.nodes.get('[data-public-first="2"]').textContent, '100.0%');

  page = await checkLoading(ok(publicData), ok(overallData), { ok: false }, realSecond);
  page.buttons.tokens.click();
  assert.deepEqual(indices(page), [3, 2, 0, 1], 'Missing token rates stay last when descending');
  page.buttons.tokens.click();
  assert.deepEqual(indices(page), [2, 3, 0, 1], 'Missing token rates stay last when ascending');
  page = await checkLoading({ ok: false }, ok(overallData), { ok: false }, realSecond);
  page.buttons.publicFirst.click();
  assert.deepEqual(indices(page), [2, 3, 0, 1], 'Hidden rows stay after loaded results');
  assert.equal(page.rows[0].hidden, true);
  console.log('Site aggregate, sorting, and failure handling: passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
