from types import SimpleNamespace

import pytest

from scripts.probe_codex_readonly import classify, run_probe


@pytest.mark.parametrize('host_code,host,sandbox_code,sandbox,want', [
    (0,'inside:read\noutside:read\n',0,'inside:read\noutside:read\n','OUTSIDE_READABLE'),
    (0,'inside:read\noutside:read\n',0,'inside:read\noutside:denied\n','OUTSIDE_DENIED_IN_PROBE'),
    (1,'inside:read\noutside:read\n',0,'inside:read\noutside:denied\n','INCONCLUSIVE'),
    (0,'inside:read\noutside:read\n',1,'inside:read\noutside:denied\n','INCONCLUSIVE'),
    (0,'inside:read\noutside:read\n',0,'inside:denied\noutside:denied\n','INCONCLUSIVE'),
])
def test_probe_requires_valid_host_and_inside_controls(host_code,host,sandbox_code,sandbox,want):
    assert classify(host_code,host,sandbox_code,sandbox) == want


def test_probe_keeps_only_sanitized_markers_and_never_calls_model(tmp_path):
    calls = []
    def runner(argv,**kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0,stdout='inside:read\noutside:read\nprivate-noise\n')
    result = run_probe(tmp_path/'probe',codex='codex-test',powershell='powershell-test',runner=runner)
    assert result['result'] == 'OUTSIDE_READABLE' and result['model_call'] is False
    assert 'private-noise' not in (tmp_path/'probe/receipt.json').read_text(encoding='utf-8')
    assert calls[1][:2] == ['codex-test','sandbox'] and ':read-only' in calls[1]
