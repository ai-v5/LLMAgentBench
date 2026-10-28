const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { derive } = require('../site/app.js');

const root = path.resolve(__dirname, '..');
const source = JSON.parse(fs.readFileSync(path.join(root, 'results/engineering-overall-r3/summary.json'), 'utf8'));
const result = derive(source);
assert.equal(result.caseCount, source.case_count);
assert.equal(result.repeats, source.repeats);
assert.equal(result.totalAttempts, source.candidates.reduce((sum, row) => sum + row.assigned, 0));
for (let i = 0; i < result.rows.length; i++) {
  assert.equal(result.rows[i].first, source.candidates[i].first_passed / source.candidates[i].assigned * 100);
  assert.equal(result.rows[i].final, source.candidates[i].passed / source.candidates[i].assigned * 100);
  assert.equal(result.rows[i].throughput, source.candidates[i].effective_passes_per_hour);
  assert.equal(result.rows[i].total, source.candidates[i].attempt_seconds);
  assert.deepEqual(result.rows[i].outcomes, ['failed', 'unscored', 'errors', 'timeouts'].map(key => source.candidates[i][key]));
}
const invalid = structuredClone(source);
invalid.candidates[0].failed += 1;
assert.throws(() => derive(invalid), /Invalid candidate aggregate/);
const wrongRate = structuredClone(source);
wrongRate.candidates[0].effective_passes_per_hour += 1;
assert.throws(() => derive(wrongRate), /Invalid candidate aggregate/);
const fixture = structuredClone(source);
fixture.candidates[0].evidence = 'FIXTURE_SMOKE';
assert.throws(() => derive(fixture), /Invalid candidate aggregate/);

async function checkFailure(response) {
  const error = { hidden: true };
  const region = { busy: true, setAttribute(name, value) { if (name === 'aria-busy') this.busy = value !== 'false'; } };
  const document = { getElementById: () => error, querySelectorAll: () => [region] };
  const code = fs.readFileSync(path.join(root, 'site/app.js'), 'utf8');
  vm.runInNewContext(code, { document, fetch: async () => response });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(error.hidden, false);
  assert.equal(region.busy, false);
}

(async () => {
  await checkFailure({ ok: false });
  await checkFailure({ ok: true, json: async () => invalid });
  console.log('Site aggregate contract and failure handling: passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
