"""Run only evaluator-configured commands; terminate only their own process tree."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def child_env(pass_env: list[str] = ()) -> dict[str, str]:
    names = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "CODEX_HOME", "DSH_HOME", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "LANG", "LC_ALL"}
    names.update(name.upper() for name in pass_env)
    return {key: value for key, value in os.environ.items() if key.upper() in names}


def execute(argv: list[str], *, cwd: Path, stdin: str, timeout: float, pass_env: list[str] = (), extra_env: dict | None = None) -> dict:
    environment = child_env(pass_env)
    environment.update(extra_env or {})
    process = subprocess.Popen(
        argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=environment,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            # A detached child can keep the inherited pipes open after the
            # launcher is killed. The timed-out call is already terminal; do
            # not block the evaluator on those pipes or serialize their raw
            # contents.
            try:
                process.kill()
            except OSError:
                pass
            stdout, stderr = "", ""
    return {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr, "timed_out": timed_out}
