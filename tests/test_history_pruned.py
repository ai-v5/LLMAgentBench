"""Historical mixed exports retain other models without superseded candidate rows."""
import json
from pathlib import Path

from llmagentbench.contracts import digest


ROOT = Path(__file__).resolve().parents[1]
MIXED_EXPORTS = {
    'engineering-overall-ale-r1/sol-luna-summary.json': 'Codex GPT-6.1 Sol',
    'engineering-overall-ale-r1/terra-dsh-summary.json': 'DSH V4.1 Flash 1017',
    'engineering-overall-case-retest-r1/sol-luna-summary.json': 'Codex GPT-6.1 Sol',
    'engineering-overall-case-retest-r1/terra-dsh-summary.json': 'DSH V4.1 Flash 1017',
    'engineering-overall-luna-sol-r1/summary.json': 'Codex GPT-6.1 Sol',
    'engineering-overall-r3/summary.json': 'DSH V4.1 Flash 1017',
    'engineering-public-luna-sol-r1/summary.json': 'Codex GPT-6.1 Sol',
    'engineering-public-luna-sol-r1/token-usage.json': 'Codex GPT-6.1 Sol',
    'engineering-public-r3/summary.json': 'DSH V4.1 Flash 1017',
    'engineering-public-r3/token-usage.json': 'DSH V4.1 Flash 1017',
    'terra-1017-public-r1/summary.json': 'dsh-flash-max',
}
REPORTS = (
    'engineering-overall-ale-r1/report.md',
    'engineering-overall-case-retest-r1/report.md',
    'engineering-overall-luna-sol-r1/report.md',
    'engineering-overall-r3/report.md',
    'engineering-public-luna-sol-r1/report.md',
    'engineering-public-r3/report.md',
    'terra-1017-public-r1/report.md',
)


def test_shared_old_exports_only_retain_unrelated_candidates():
    for filename, label in MIXED_EXPORTS.items():
        data = json.loads((ROOT / 'results' / filename).read_text(encoding='utf-8'))
        assert [row.get('label', row.get('candidate_id')) for row in data['candidates']] == [label]
        if 'export_sha256' in data:
            expected = data.pop('export_sha256')
            assert digest(data) == expected


def test_shared_old_reports_omit_replaced_candidate_rows():
    for filename in REPORTS:
        text = (ROOT / 'results' / filename).read_text(encoding='utf-8').lower()
        rows = [line for line in text.splitlines() if line.startswith('| ')]
        assert all('gpt-6.1 terra' not in line and 'gpt-6 luna' not in line
                   and 'codex-terra' not in line and 'codex-luna' not in line for line in rows)
        assert '来源收据对应当时的完整运行' in text
