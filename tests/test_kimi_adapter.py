import json
from pathlib import Path

import pytest

from llmagentbench import adapters
from llmagentbench.contracts import ContractError, validate_adapter


def wire_events(*, tool=False, model="k3d1-agent", effort="max"):
    events = [
        {"type": "profile.bind", "modelAlias": model, "thinkingEffort": effort},
        {"type": "llm.tools_snapshot", "tools": [{"name": "synthetic-tool"}]},
        {"type": "llm.request", "model": model, "thinkingEffort": effort, "toolSelect": True},
    ]
    if tool:
        events.append({"type": "tool.call", "name": "synthetic-private-marker"})
    events += [
        {"type": "usage.record", "usage": {"inputOther": 7, "output": 3, "private": "omit"}},
        {"type": "agent.turn.ended", "outcome": "done"},
        {"type": "prompt.completed", "reason": "completed"},
    ]
    return events


def write_wire(root: Path, *, tool=False, model="k3d1-agent", effort="max") -> None:
    path = root / "session" / "agents" / "main" / "wire.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(item) for item in wire_events(tool=tool, model=model, effort=effort)) + "\n", encoding="utf-8")


def test_kimi_wire_audit_accepts_clean_turn_without_retaining_private_payload(tmp_path):
    write_wire(tmp_path)
    result = adapters.audit_kimi_wire({}, tmp_path, "k3d1-agent", "max")
    assert result["status"] == "no_tool_events_reported"
    assert result["effective_model"] == "k3d1-agent"
    assert result["effective_reasoning_effort"] == "max"
    assert result["usage"] == {"inputOther": 7, "output": 3}
    assert "private" not in json.dumps(result)


def test_kimi_wire_audit_rejects_reported_tool_activity_without_payload(tmp_path):
    write_wire(tmp_path, tool=True)
    result = adapters.audit_kimi_wire({}, tmp_path, "k3d1-agent", "max")
    assert result["status"] == "tool_event_reported"
    assert result["tool_event_count"] == 1
    assert "synthetic-private-marker" not in json.dumps(result)


def test_kimi_stdout_parser_ignores_daimon_logs():
    text = "2026-10-31T00:00:00Z INFO standalone-runtime startup complete\n" \
           + "{\"answer\":\"ok\",\"files\":[]}\n" \
           + "2026-10-31T00:00:01Z INFO standalone-runtime shutdown complete\n"
    assert adapters.parse_kimi_stdout(text) == {"answer": "ok", "files": []}


def test_kimi_invoke_binds_model_effort_and_wire_audit(tmp_path, monkeypatch):
    config = tmp_path / "kimi-config.json"
    config.write_text("{}", encoding="utf-8")
    wire_root = tmp_path / "wire"
    monkeypatch.setenv("TEST_KIMI_LAUNCHER", json.dumps(["powershell.exe", "-File", "synthetic.ps1"]))
    monkeypatch.setenv("TEST_KIMI_CONFIG", str(config))
    monkeypatch.setenv("TEST_KIMI_WIRE_ROOT", str(wire_root))

    def fake_execute(argv, **kwargs):
        assert argv[argv.index("--config") + 1] == str(config.resolve())
        assert argv[argv.index("--model") + 1] == "k3d1-agent"
        assert argv[argv.index("--thinking") + 1] == "max"
        assert Path(argv[argv.index("--prompt-file") + 1]).read_text(encoding="utf-8").startswith("Complete the supplied task.")
        write_wire(wire_root)
        return {"exit_code": 0, "timed_out": False,
                "stdout": json.dumps({"answer": "ok", "files": []}), "stderr": ""}

    monkeypatch.setattr(adapters, "execute", fake_execute)
    candidate = {
        "adapter": "kimi", "model": "k3d1-agent", "reasoning_effort": "max",
        "local_lookup_audit": "kimi_wire_v1", "launcher_env": "TEST_KIMI_LAUNCHER",
        "config_env": "TEST_KIMI_CONFIG", "wire_root_env": "TEST_KIMI_WIRE_ROOT",
    }
    call = adapters.invoke(candidate, {"case_id": "x", "round": 0}, tmp_path, tmp_path / "control", 5)
    assert call["status"] == "ok"
    assert call["response"] == {"answer": "ok", "files": []}
    assert call["effective_model"] == "k3d1-agent"
    assert call["effective_reasoning_effort"] == "max"
    assert call["usage"]["output"] == 3
    assert call["observed_model"] is None


def test_kimi_invoke_rejects_tool_event(tmp_path, monkeypatch):
    config = tmp_path / "kimi-config.json"
    config.write_text("{}", encoding="utf-8")
    wire_root = tmp_path / "wire"
    monkeypatch.setenv("TEST_KIMI_LAUNCHER", json.dumps(["powershell.exe", "-File", "synthetic.ps1"]))
    monkeypatch.setenv("TEST_KIMI_CONFIG", str(config))
    monkeypatch.setenv("TEST_KIMI_WIRE_ROOT", str(wire_root))

    def fake_execute(argv, **kwargs):
        write_wire(wire_root, tool=True)
        return {"exit_code": 0, "timed_out": False,
                "stdout": json.dumps({"answer": "ok", "files": []}), "stderr": ""}

    monkeypatch.setattr(adapters, "execute", fake_execute)
    candidate = {
        "adapter": "kimi", "model": "k3d1-agent", "reasoning_effort": "max",
        "local_lookup_audit": "kimi_wire_v1", "launcher_env": "TEST_KIMI_LAUNCHER",
        "config_env": "TEST_KIMI_CONFIG", "wire_root_env": "TEST_KIMI_WIRE_ROOT",
    }
    call = adapters.invoke(candidate, {"case_id": "x", "round": 0}, tmp_path, tmp_path / "control", 5)
    assert call["status"] == "error"
    assert call["response"] is None
    assert call["local_lookup_audit"]["status"] == "tool_event_reported"
    assert "synthetic-private-marker" not in json.dumps(call)


def test_kimi_invoke_fails_closed_when_wire_is_missing(tmp_path, monkeypatch):
    config = tmp_path / "kimi-config.json"
    config.write_text("{}", encoding="utf-8")
    wire_root = tmp_path / "wire"
    monkeypatch.setenv("TEST_KIMI_LAUNCHER", json.dumps(["powershell.exe", "-File", "synthetic.ps1"]))
    monkeypatch.setenv("TEST_KIMI_CONFIG", str(config))
    monkeypatch.setenv("TEST_KIMI_WIRE_ROOT", str(wire_root))
    monkeypatch.setattr(adapters, "execute", lambda *args, **kwargs: {
        "exit_code": 0, "timed_out": False,
        "stdout": json.dumps({"answer": "ok", "files": []}), "stderr": "",
    })
    candidate = {
        "adapter": "kimi", "model": "k3d1-agent", "reasoning_effort": "max",
        "local_lookup_audit": "kimi_wire_v1", "launcher_env": "TEST_KIMI_LAUNCHER",
        "config_env": "TEST_KIMI_CONFIG", "wire_root_env": "TEST_KIMI_WIRE_ROOT",
    }
    call = adapters.invoke(candidate, {"case_id": "x", "round": 0}, tmp_path, tmp_path / "control", 5)
    assert call["status"] == "error"
    assert call["local_lookup_audit"]["status"] == "inconclusive"


def test_kimi_identity_freezes_launcher_and_config_hash(tmp_path, monkeypatch):
    config = tmp_path / "kimi-config.json"
    config.write_text("synthetic-config", encoding="utf-8")
    monkeypatch.setenv("TEST_KIMI_LAUNCHER", json.dumps(["powershell.exe", "-File", "synthetic.ps1"]))
    monkeypatch.setenv("TEST_KIMI_CONFIG", str(config))
    candidate = {"id": "kimi", "adapter": "kimi", "model": "k3d1-agent", "reasoning_effort": "max",
                 "local_lookup_audit": "kimi_wire_v1", "launcher_env": "TEST_KIMI_LAUNCHER",
                 "config_env": "TEST_KIMI_CONFIG"}
    identity = adapters.adapter_identity(candidate)
    assert identity["local_lookup_audit"] == "kimi_wire_events"
    assert identity["sandbox"] == "not_verified"
    assert identity["config_file_sha256"]


def test_kimi_identity_accepts_explicit_startup_config_hash(tmp_path, monkeypatch):
    config = tmp_path / "kimi-config.json"
    config.write_text("synthetic-config", encoding="utf-8")
    monkeypatch.setenv("TEST_KIMI_LAUNCHER", json.dumps(["powershell.exe", "-File", "synthetic.ps1"]))
    monkeypatch.setenv("TEST_KIMI_CONFIG", str(config))
    frozen = "a" * 64
    candidate = {"id": "kimi", "adapter": "kimi", "model": "k3d1-agent", "reasoning_effort": "max",
                 "local_lookup_audit": "kimi_wire_v1", "config_env": "TEST_KIMI_CONFIG",
                 "launcher_env": "TEST_KIMI_LAUNCHER", "config_identity_sha256": frozen}
    assert adapters.adapter_identity(candidate)["config_file_sha256"] == frozen


def test_kimi_contract_rejects_invalid_startup_config_hash():
    good = {"adapter": "kimi", "model": "k3d1-agent", "reasoning_effort": "max",
            "local_lookup_audit": "kimi_wire_v1"}
    with pytest.raises(ContractError):
        validate_adapter({**good, "config_identity_sha256": "not-a-sha"})


def test_kimi_contract_requires_explicit_audit_and_effort():
    good = {"adapter": "kimi", "model": "k3d1-agent", "reasoning_effort": "max",
            "local_lookup_audit": "kimi_wire_v1"}
    validate_adapter(good)
    with pytest.raises(ContractError):
        validate_adapter({**good, "local_lookup_audit": "none"})
    with pytest.raises(ContractError):
        validate_adapter({k: v for k, v in good.items() if k != "reasoning_effort"})
