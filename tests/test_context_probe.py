import json
from types import SimpleNamespace

from scripts.probe_codex_context import GLOBAL_MARKER, PROJECT_MARKER, classify, run_probe


def test_context_probe_requires_positive_controls():
    assert classify({'global':True,'project':True},{'global':True,'project':False}) == 'GLOBAL_NOT_CAPPED'
    assert classify({'global':False,'project':True},{'global':False,'project':False}) == 'INCONCLUSIVE'
    assert classify({'global':True,'project':True},{}) == 'INCONCLUSIVE'


def test_context_probe_is_synthetic_and_does_not_record_prompt(tmp_path):
    calls = []
    def runner(argv,**kwargs):
        calls.append((argv,kwargs))
        text = GLOBAL_MARKER + (PROJECT_MARKER if 'project_doc_max_bytes=32000' in argv else '')
        return SimpleNamespace(returncode=0,stdout=json.dumps([{'type':'message','text':text+' private-noise'}]))
    result = run_probe(tmp_path/'context',codex='codex-test',runner=runner)
    assert result['result'] == 'GLOBAL_NOT_CAPPED' and result['model_call'] is False
    assert all('debug' in argv and 'prompt-input' in argv for argv,_ in calls)
    assert all(str(kwargs['env']['CODEX_HOME']).startswith(str(tmp_path)) for _,kwargs in calls)
    saved = (tmp_path/'context/receipt.json').read_text(encoding='utf-8')
    assert 'private-noise' not in saved and GLOBAL_MARKER not in saved and PROJECT_MARKER not in saved
