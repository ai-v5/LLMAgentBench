const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { derive } = require('../site/app.js');

const root = path.resolve(__dirname, '..');
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
const publicData = read('results/engineering-public-r3/summary.json');
const overallData = read('results/engineering-overall-r3/summary.json');
const usage = read('results/engineering-public-r3/token-usage.json');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const table = html.match(/<table class="results-table">([\s\S]*?)<\/table>/);
assert.ok(table, 'The results must remain a semantic table');
assert.equal((html.match(/<table\b/g) || []).length, 1);
assert.equal((table[1].match(/scope="col"/g) || []).length, 4);
assert.equal((table[1].match(/data-result-row=/g) || []).length, publicData.candidates.length);
for (const field of ['data-public-first', 'data-public-final', 'data-all-first', 'data-all-final', 'data-token-rate']) {
  assert.equal((table[1].match(new RegExp(field + '=', 'g')) || []).length, publicData.candidates.length, field);
}
const result = derive(publicData, overallData, usage);
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

async function checkLoading(publicResponse, overallResponse, tokenResponse) {
  const alerts = { 'data-error': { hidden: true }, 'token-error': { hidden: true } };
  const region = { busy: true, setAttribute(name, value) { if (name === 'aria-busy') this.busy = value !== 'false'; } };
  const nodes = new Map();
  const document = {
    getElementById: (id) => alerts[id],
    querySelectorAll: (selector) => {
      if (selector === '[data-data-region]') return [region];
      if (!nodes.has(selector)) nodes.set(selector, { textContent: '' });
      return [nodes.get(selector)];
    },
  };
  const code = fs.readFileSync(path.join(root, 'site/app.js'), 'utf8');
  const fetch = async (url) => url.includes('token-usage') ? tokenResponse : url.includes('engineering-public') ? publicResponse : overallResponse;
  vm.runInNewContext(code, { document, fetch });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(region.busy, false);
  return { alerts, nodes };
}

const ok = (value) => ({ ok: true, json: async () => value });
(async () => {
  let page = await checkLoading({ ok: false }, ok(overallData), { ok: false });
  assert.equal(page.alerts['data-error'].hidden, false);
  page = await checkLoading(ok(publicData), ok(overallData), { ok: false });
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, false);
  assert.equal(page.nodes.get('[data-public-first="0"]').textContent, '100.0%');
  assert.equal(page.nodes.get('[data-token-rate="0"]').textContent, '未记录');
  page = await checkLoading(ok(publicData), ok(overallData), ok(wrongScope));
  assert.equal(page.alerts['token-error'].hidden, false);
  assert.equal(page.nodes.get('[data-token-rate="0"]').textContent, '未记录');
  page = await checkLoading(ok(publicData), ok(overallData), ok(usage));
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, true);
  assert.equal(page.nodes.get('[data-token-rate="0"]').textContent, (12448 / 1357.219).toFixed(2));
  assert.equal(page.nodes.get('[data-all-first="0"]').textContent, (45 / 46 * 100).toFixed(1) + '%');
  console.log('Site aggregate contract and failure handling: passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
