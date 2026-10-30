from scripts.probe_codex_tool_events import classify, classify_disabled, find_exec


def test_tool_event_probe_requires_an_observed_sentinel_read():
    assert classify(False,'tool_event_reported',True) == 'INCONCLUSIVE'
    assert classify(True,'tool_event_reported',False) == 'INCONCLUSIVE'
    assert classify(True,'tool_event_reported',True) == 'TOOL_EVENT_DETECTED'
    assert classify(True,'no_tool_events_reported',True) == 'TOOL_EVENT_NOT_DETECTED'


def test_tool_event_probe_finds_namespaced_custom_tool():
    assert find_exec([{'type':'namespace','name':'functions','tools':[{'name':'exec'}]}]) == ('exec','functions')
    assert find_exec([{'name':'exec_command'}]) == ('exec_command',None)
    assert find_exec([{'name':'other'}]) is None


def test_disabled_command_probe_never_treats_missing_request_as_denial():
    assert classify_disabled(False,1,False) == 'INCONCLUSIVE'
    assert classify_disabled(False,2,False) == 'INCONCLUSIVE'
    assert classify_disabled(False,2,True) == 'COMMAND_READ_NOT_OBSERVED'
    assert classify_disabled(True,2,True) == 'COMMAND_READ_OBSERVED'
