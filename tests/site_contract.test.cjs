const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { derive } = require('../site/app.js');

const root = path.resolve(__dirname, '..');
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));

const ROWS = 16;
const EXP = [
  ['flex', 'low', 'DSH V4.1 Flash 1017 Flex', 'ds-v4.1-flash-1017-flex', 8],
  ['flex', 'high', 'DSH V4.1 Flash 1017 Flex', 'ds-v4.1-flash-1017-flex', 9],
  ['flex', 'max', 'DSH V4.1 Flash 1017 Flex', 'ds-v4.1-flash-1017-flex', 10],
  ['glm', 'low', 'GLM 5.3', 'glm5.3', 11],
  ['glm', 'high', 'GLM 5.3', 'glm5.3', 12],
  ['glm', 'max', 'GLM 5.3', 'glm5.3', 13],
  ['speedup', 'max', 'DSH V4.1 Flash 1017 SpeedUp', 'speedup10x', 15],
];

const hex = (letter) => letter.repeat(64);

const kimiPublic = read('results/engineering-kimi-public-r1/summary.json');
const kimiOverall = read('results/engineering-kimi-overall-r1/summary.json');
const kimiTokens = read('results/engineering-kimi-public-r1/token-usage.json');
const kimiProvenance = read('results/engineering-kimi-overall-r1/provenance.json');

function effortBatches(directory, efforts = ['max', 'high', 'low']) {
  const out = {};
  for (const effort of efforts) {
    out[effort] = {
      summary: read(`results/${directory}/${effort}/summary.json`),
      overall: read(`results/${directory}/${effort}/overall.json`),
      tokens: read(`results/${directory}/${effort}/token-usage.json`),
      provenance: read(`results/${directory}/${effort}/provenance.json`),
      overallProvenance: read(`results/${directory}/${effort}/overall-provenance.json`),
    };
  }
  return out;
}

const terra = effortBatches('terra-20261111-standard');
const luna = effortBatches('luna-20261111-standard');
const sol = effortBatches('sol-20261111-standard', ['max', 'low']);

for (const effort of ['max', 'low']) {
  const entry = sol[effort];
  assert.equal(entry.summary.pack_version, '20261111');
  assert.equal(entry.summary.case_count, 13);
  assert.equal(entry.summary.repeats, 2);
  assert.equal(entry.summary.candidates[0].assigned, 26);
  assert.equal(entry.overall.case_count, 91);
  assert.equal(entry.overall.candidates[0].assigned, 104);
  assert.equal(entry.provenance.requested_model, 'gpt-6.1-sol');
  assert.equal(entry.provenance.reasoning_effort, effort);
  assert.equal(entry.provenance.source_receipts_reverified_now, true);
  assert.equal(entry.provenance.selection_granularity, 'case_repeat');
  assert.equal(entry.provenance.sources.reduce((sum, source) => sum + source.selected_assignments, 0), 26);
  assert.deepEqual(entry.tokens.source_receipt_sha256.slice().sort(),
    entry.provenance.sources.map((source) => source.receipt_sha256).sort());
}

function candidate(label, assigned, first, passed, hours) {
  const attempt = hours * 3600;
  const failed = assigned - passed;
  return {
    label, evidence: 'MODEL_RUN', assigned, first_passed: first, passed,
    failed, unscored: 0, errors: 0, timeouts: 0,
    attempt_seconds: attempt, candidate_call_seconds: attempt * 0.8,
    judge_call_seconds: attempt * 0.1, mean_attempt_seconds: attempt / assigned,
    mean_pass_seconds: attempt / Math.max(passed, 1),
    effective_passes_per_hour: passed * 3600 / attempt,
  };
}

function synthetic(tag, effort, label, model) {
  const name = `${label} ${effort}`;
  return {
    summary: {
      schema_version: 1, case_count: 13, repeats: 1, pack_version: '20261111',
      candidates: [candidate(name, 13, 11, 12, 0.05)],
    },
    overall: {
      schema_version: 2, case_count: 91, denominator: 'assigned_attempts', pack_version: '20261111',
      candidates: [candidate(name, 91, 80, 85, 0.6)],
    },
    tokens: {
      schema_version: 2, case_count: 13, repeats: 1,
      source_receipt_sha256: [hex('a')], engine_sha256: hex('b'), config_sha256: hex('c'),
      candidates: [{ label: name, candidate_id: `${tag}-${effort}`, adapter: 'dsh',
        requested_model: model, reasoning_effort: effort, evidence_level: 'MODEL_RUN',
        assigned: 13, candidate_calls: 13, usage_calls: 13, output_tokens: 5200,
        usage_call_seconds: 144, candidate_call_seconds: 144 }],
    },
    provenance: {
      schema_version: 1, visibility: 'public', synthetic: true, source_receipts_verified: true,
      case_count: 13, repeats: 1, pack_version: '20261111', requested_model: model,
      reasoning_effort: effort, mixed_conditions: false, target_pack_sha256: hex('d'),
      sources: [{ selected_cases: 13, receipt_sha256: hex('a') }],
    },
    overallProvenance: {
      schema_version: 1, authorized_private_overall: true, private_details_exported: false,
      assigned_attempts_verified: true, denominator: 'assigned_attempts', requested_models: [model],
    },
  };
}

const exp = {};
for (const [tag, effort, label, model, offset] of EXP) {
  exp[`${tag}-${effort}`] = { offset, entry: synthetic(tag, effort, label, model) };
}

const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const table = html.match(/<table class="results-table">([\s\S]*?)<\/table>/);
assert.ok(table, 'The results must remain a semantic table');
assert.equal((html.match(/<table\b/g) || []).length, 1);
assert.equal((table[1].match(/scope="col"/g) || []).length, 4);
assert.equal((table[1].match(/data-result-row=/g) || []).length, ROWS);
for (const key of ['label', 'publicFirst', 'overallFirst', 'tokens']) {
  assert.match(table[1], new RegExp('<button[^>]*type="button"[^>]*data-sort-key="' + key + '"'));
}
for (const field of ['data-public-first', 'data-public-final', 'data-all-first', 'data-all-final',
  'data-token-rate', 'data-pack']) {
  assert.equal((table[1].match(new RegExp(field + '=', 'g')) || []).length, ROWS, field);
}
assert.doesNotMatch(table[1], /engineering-1017-efforts/, 'Old 1017 rows must be gone');
assert.doesNotMatch(html, /engineering-public-luna-sol-r1/, 'The old Sol result must not be linked');
const report = fs.readFileSync(path.join(root, 'results/20261111-model-results.md'), 'utf8');
const oldReport = fs.readFileSync(path.join(root, 'results/engineering-overall-ale-r1/report.md'), 'utf8');
assert.match(report, /部分 Sol 新增样本与其他模型评测的执行窗口重叠/);
assert.match(report, /对 Sol 候选而言，评分是同模型的独立调用/);
assert.doesNotMatch(oldReport, /^\| Codex GPT-6\.1 Sol \|/m, 'The old linked report must not retain the Sol row');

const ok = (value) => ({ ok: true, json: async () => value });
const fail = () => ({ ok: false, json: async () => ({}) });

function deriveAll(overrides = {}) {
  const rows = {};
  rows[0] = derive(sol.max.summary, sol.max.overall, sol.max.tokens).rows[0];
  rows[14] = derive(sol.low.summary, sol.low.overall, sol.low.tokens).rows[0];
  rows[1] = derive(kimiPublic, kimiOverall, kimiTokens).rows[0];
  ['max', 'high', 'low'].forEach((effort, index) => {
    rows[2 + index] = derive(terra[effort].summary, terra[effort].overall, terra[effort].tokens).rows[0];
    rows[5 + index] = derive(luna[effort].summary, luna[effort].overall, luna[effort].tokens).rows[0];
  });
  for (const [, , , , offset] of EXP) {
    const key = `${EXP.find((entry) => entry[4] === offset)[0]}-${EXP.find((entry) => entry[4] === offset)[1]}`;
    const entry = overrides[key] || exp[key].entry;
    rows[offset] = derive(entry.summary, entry.overall, entry.tokens).rows[0];
  }
  return rows;
}

const expectedOrder = (rows, valueOf, direction) => {
  const items = Object.keys(rows).map(Number).map((index) => ({ index, value: valueOf(rows[index]) }));
  items.sort((left, right) => {
    const a = left.value, b = right.value;
    if (a == null || b == null) return a == null && b == null ? left.index - right.index : a == null ? 1 : -1;
    const comparison = typeof a === 'string'
      ? a.localeCompare(b, 'en', { numeric: true, sensitivity: 'base' }) : a - b;
    return (direction === 'ascending' ? comparison : -comparison) || left.index - right.index;
  });
  return items.map((item) => item.index);
};

async function load({ overrides = {}, failTokens = false } = {}) {
  const alerts = { 'data-error': { hidden: true }, 'token-error': { hidden: true } };
  const region = { busy: true, setAttribute(name, value) { if (name === 'aria-busy') this.busy = value !== 'false'; } };
  const nodes = new Map();
  const rows = [];
  for (let index = 0; index < ROWS; index += 1) {
    rows[index] = { hidden: true, getAttribute: (name) => name === 'data-result-row' ? String(index) : null };
  }
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
    return [key, { dataset: { sortKey: key }, header, closest: () => header,
      addEventListener(name, handler) { if (name === 'click') this.click = handler; } }];
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
      if (selector === '[data-sort-key]' || selector === 'th .sort-button' || selector === '.sort-button') return Object.values(buttons);
      if (selector === '.results-table tbody tr') return order.slice();
      const field = selector.match(/^\[(data-[a-z-]+)="(\d+)"\]$/);
      if (field) {
        const key = `${field[1]}:${field[2]}`;
        if (!nodes.has(key)) nodes.set(key, { textContent: '' });
        return [nodes.get(key)];
      }
      if (selector === '[data-result-row]') return order.slice();
      return [];
    },
  };
  const fetch = async (url) => {
    const solMatch = url.match(/sol-20261111-standard\/(max|low)\/(summary|overall|token-usage|provenance|overall-provenance)\.json/);
    if (solMatch) {
      const entry = overrides[`sol-${solMatch[1]}`] || sol[solMatch[1]];
      const key = { summary: 'summary', overall: 'overall', 'token-usage': 'tokens',
        provenance: 'provenance', 'overall-provenance': 'overallProvenance' }[solMatch[2]];
      return ok(entry[key]);
    }
    const expMatch = url.match(/exp-20261111\/(1017|flex|glm|speedup)\/(low|high|max)\/(summary|overall|token-usage|provenance|overall-provenance)\.json/);
    if (expMatch) {
      const entry = overrides[`${expMatch[1]}-${expMatch[2]}`] || exp[`${expMatch[1]}-${expMatch[2]}`].entry;
      const key = { summary: 'summary', overall: 'overall', 'token-usage': 'tokens',
        provenance: 'provenance', 'overall-provenance': 'overallProvenance' }[expMatch[3]];
      if (key === 'tokens' && failTokens) return fail();
      return ok(entry[key]);
    }
    const effortMatch = url.match(/(terra|luna)-20261111-standard\/(max|high|low)\/(summary|overall|token-usage|provenance|overall-provenance)\.json/);
    if (effortMatch) {
      const source = effortMatch[1] === 'terra' ? terra : luna;
      const key = { summary: 'summary', overall: 'overall', 'token-usage': 'tokens',
        provenance: 'provenance', 'overall-provenance': 'overallProvenance' }[effortMatch[3]];
      const entry = overrides[`${effortMatch[1]}-${effortMatch[2]}`] || source[effortMatch[2]];
      return ok(entry[key]);
    }
    if (url.includes('engineering-kimi-public-r1/summary.json')) return ok(kimiPublic);
    if (url.includes('engineering-kimi-overall-r1/summary.json')) return ok(kimiOverall);
    if (url.includes('engineering-kimi-public-r1/token-usage.json')) return ok(kimiTokens);
    if (url.includes('engineering-kimi-overall-r1/provenance.json')) return ok(kimiProvenance);
    throw new Error('Unexpected fetch: ' + url);
  };
  vm.runInNewContext(fs.readFileSync(path.join(root, 'site/app.js'), 'utf8'), { document, fetch });
  const deadline = Date.now() + 5000;
  while (region.busy && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.equal(region.busy, false, 'The page must finish loading every batch');
  const indices = () => order.map((row) => Number(row.getAttribute('data-result-row')));
  const text = (selector) => nodes.get(selector.replace('[', '').replace(']', '').replace('"', ':').replace('"', ''))?.textContent;
  return { alerts, rows, buttons, indices, nodes };
}

(async () => {
  let page = await load();
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.alerts['token-error'].hidden, true);
  assert.equal(page.rows.every((row) => !row.hidden), true, 'Every batch must load');

  const rows = deriveAll();
  const labels = page.indices().map((index) => page.nodes.get(`data-name:${index}`).textContent);
  for (const [, effort, label, , ] of EXP) {
    assert.ok(labels.some((value) => value === `${label} ${effort}`), 'missing label ' + label + ' ' + effort);
  }
  assert.ok(labels.includes('Codex GPT-6.1 Sol max'));
  assert.ok(labels.includes('Codex GPT-6.1 Sol low'));
  assert.ok(!labels.includes('Codex GPT-6.1 Sol'), 'The old unversioned Sol row must be gone');
  assert.ok(labels.includes('Kimi K3.1 Pro'));
  assert.ok(!labels.includes('DSH V4.1 Flash 1017'), 'The unversioned 1017 row must stay removed');

  assert.equal(page.nodes.get('data-pack:8').textContent, '题库 20261111');
  assert.equal(page.nodes.get('data-pack:0').textContent, '题库 20261111');
  assert.equal(page.nodes.get('data-pack:14').textContent, '题库 20261111');

  // The issue note must lead with failed so a row cannot look clean while it failed cases.
  const flexMax = rows[10];
  const flexMaxPublic = exp['flex-max'].entry.summary.candidates[0];
  assert.equal(page.nodes.get('data-public-final:10').textContent,
    `含修复 ${flexMax.publicFinal.toFixed(1)}% · 失败/未评分/错误/超时 ` +
    `${flexMaxPublic.failed}/${flexMaxPublic.unscored}/${flexMaxPublic.errors}/${flexMaxPublic.timeouts}`);
  assert.match(page.nodes.get('data-all-final:10').textContent, /失败\/未评分\/错误\/超时 \d+\/\d+\/\d+\/\d+$/);

  assert.deepEqual(page.indices(), expectedOrder(rows, (row) => row.overallFirst, 'descending'));
  page.buttons.publicFirst.click();
  assert.deepEqual(page.indices(), expectedOrder(rows, (row) => row.publicFirst, 'descending'));
  page.buttons.publicFirst.click();
  assert.deepEqual(page.indices(), expectedOrder(rows, (row) => row.publicFirst, 'ascending'));
  page.buttons.tokens.click();
  assert.deepEqual(page.indices(), expectedOrder(rows, (row) => (row.tokens ? row.tokens.rate : null), 'descending'));
  page.buttons.label.click();
  assert.deepEqual(page.indices(), expectedOrder(rows, (row) => row.label, 'ascending'));

  const brokenProvenance = structuredClone(exp['glm-max'].entry);
  brokenProvenance.provenance.private_details_exported = false;
  brokenProvenance.provenance.requested_model = 'gpt-6-luna';
  page = await load({ overrides: { 'glm-max': brokenProvenance } });
  assert.equal(page.alerts['data-error'].hidden, false, 'A wrong model in provenance must be rejected');
  assert.equal(page.rows[13].hidden, true);
  assert.equal(page.rows[8].hidden, false);

  const wrongAssignments = structuredClone(sol.max);
  wrongAssignments.provenance.sources[0].selected_assignments -= 1;
  page = await load({ overrides: { 'sol-max': wrongAssignments } });
  assert.equal(page.alerts['data-error'].hidden, false, 'Missing Sol assignment must be rejected');
  assert.equal(page.rows[0].hidden, true);
  assert.equal(page.rows[14].hidden, false);

  const wrongGranularity = structuredClone(sol.max);
  wrongGranularity.provenance.selection_granularity = 'unknown';
  page = await load({ overrides: { 'sol-max': wrongGranularity } });
  assert.equal(page.alerts['data-error'].hidden, false, 'Unknown source granularity must be rejected');
  assert.equal(page.rows[0].hidden, true);

  const staleSolSource = structuredClone(sol.max);
  staleSolSource.provenance.source_receipts_reverified_now = false;
  staleSolSource.provenance.source_publication_commit = 'a'.repeat(40);
  staleSolSource.provenance.source_pack_version = '20261110';
  staleSolSource.provenance.verification_boundary = 'historical receipt unavailable';
  page = await load({ overrides: { 'sol-max': staleSolSource } });
  assert.equal(page.alerts['data-error'].hidden, false, 'Sol must use reverified receipts');
  assert.equal(page.rows[0].hidden, true);

  const duplicateReceipt = structuredClone(sol.low);
  duplicateReceipt.provenance.sources[1].receipt_sha256 = duplicateReceipt.provenance.sources[0].receipt_sha256;
  page = await load({ overrides: { 'sol-low': duplicateReceipt } });
  assert.equal(page.alerts['data-error'].hidden, false, 'Duplicate Sol receipts must be rejected');
  assert.equal(page.rows[14].hidden, true);

  const wrongSolTokenModel = structuredClone(sol.max);
  wrongSolTokenModel.tokens.candidates[0].requested_model = 'gpt-6.1-terra';
  page = await load({ overrides: { 'sol-max': wrongSolTokenModel } });
  assert.equal(page.alerts['data-error'].hidden, false, 'Sol token usage must match the requested model');
  assert.equal(page.rows[0].hidden, true);

  const brokenHistoricalBoundary = structuredClone(terra.max);
  delete brokenHistoricalBoundary.provenance.verification_boundary;
  page = await load({ overrides: { 'terra-max': brokenHistoricalBoundary } });
  assert.equal(page.alerts['data-error'].hidden, false, 'Unavailable historical receipts require their boundary');
  assert.equal(page.rows[2].hidden, true);

  page = await load({ failTokens: true });
  assert.equal(page.alerts['token-error'].hidden, false, 'Missing token usage must be reported');
  assert.equal(page.alerts['data-error'].hidden, true);
  assert.equal(page.rows.every((row) => !row.hidden), true);
  assert.equal(page.nodes.get('data-token-rate:9').textContent, '未记录');

  const partial = structuredClone(exp['flex-max'].entry);
  Object.assign(partial.tokens.candidates[0], {
    usage_calls: 12, candidate_calls: 13, output_tokens: 2400,
    usage_call_seconds: 100, candidate_call_seconds: 144,
  });
  page = await load({ overrides: { 'flex-max': partial } });
  assert.equal(page.alerts['token-error'].hidden, true, 'Partial token coverage must still be shown');
  assert.equal(page.nodes.get('data-token-rate:10').textContent, '24.00');
  assert.match(page.nodes.get('data-token-detail:10').textContent, /12\/13 次有用量/);

  const brokenPartial = structuredClone(exp['flex-max'].entry);
  Object.assign(brokenPartial.tokens.candidates[0], {
    usage_calls: 12, candidate_calls: 13, output_tokens: 2400, candidate_call_seconds: 144,
  });
  delete brokenPartial.tokens.candidates[0].usage_call_seconds;
  page = await load({ overrides: { 'flex-max': brokenPartial } });
  assert.equal(page.alerts['token-error'].hidden, false, 'Partial coverage needs its own timing');
  assert.equal(page.nodes.get('data-token-rate:10').textContent, '未记录');

  console.log('Site aggregate, sorting, and failure handling: passed');
})().catch((error) => { console.error(error); process.exitCode = 1; });


