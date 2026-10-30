"""Probe a Windows read-only sandbox using only synthetic files.

This is a diagnostic for the named sandbox profile, not proof that a model
invocation, another backend or a different host is isolated.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _markers(output: str) -> set[str]:
    allowed = {'inside:read','inside:denied','outside:read','outside:denied'}
    return {line.strip() for line in output.splitlines() if line.strip() in allowed}


def classify(host_exit: int | None, host_output: str, sandbox_exit: int | None, sandbox_output: str) -> str:
    host = _markers(host_output)
    sandbox = _markers(sandbox_output)
    if host_exit != 0 or host != {'inside:read','outside:read'} or sandbox_exit != 0:
        return 'INCONCLUSIVE'
    if sandbox == {'inside:read','outside:read'}:
        return 'OUTSIDE_READABLE'
    if sandbox == {'inside:read','outside:denied'}:
        return 'OUTSIDE_DENIED_IN_PROBE'
    return 'INCONCLUSIVE'


def run_probe(output: Path, *, codex: str, powershell: str, runner=subprocess.run) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / 'workspace'
    workspace.mkdir()
    inside, outside = workspace / 'inside.txt', output / 'outside.txt'
    inside.write_text('synthetic-inside', encoding='utf-8')
    outside.write_text('synthetic-outside', encoding='utf-8')
    script = workspace / 'probe.ps1'
    script.write_text(
        'param([string]$Inside,[string]$Outside)\n'
        'try { Get-Content -LiteralPath $Inside -ErrorAction Stop | Out-Null; Write-Output "inside:read" } catch { Write-Output "inside:denied" }\n'
        'try { Get-Content -LiteralPath $Outside -ErrorAction Stop | Out-Null; Write-Output "outside:read" } catch { Write-Output "outside:denied" }\n',
        encoding='utf-8')
    command = [powershell,'-NoLogo','-NoProfile','-ExecutionPolicy','Bypass',
               '-File',str(script),str(inside),str(outside)]
    sandbox = [codex,'sandbox','--include-managed-config','-c','windows.sandbox="unelevated"',
               '-P',':read-only','-C',str(workspace),'--',*command]
    def execute(argv):
        try:
            result = runner(argv,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=25)
            return result.returncode,result.stdout
        except (OSError,subprocess.TimeoutExpired):
            return None,''
    host_exit,host_output = execute(command)
    sandbox_exit,sandbox_output = execute(sandbox)
    result = {'schema_version':1,'probe':'windows_unelevated_builtin_read_only',
              'model_call':False,'result':classify(host_exit,host_output,sandbox_exit,sandbox_output),
              'host_controls_ok':host_exit == 0 and _markers(host_output) == {'inside:read','outside:read'},
              'sandbox_exit_code':sandbox_exit,'sandbox_markers':sorted(_markers(sandbox_output)),
              'boundary':'Synthetic diagnostic only; the actual model invocation is not certified.'}
    (output / 'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True,help='New path under this repository .bench-runs/')
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    if sys.platform != 'win32':
        print(json.dumps({'state':'unsupported','reason':'windows_only'}))
        return 2
    target = args.out.resolve()
    if not target.is_relative_to((repository / '.bench-runs').resolve()) or target.exists():
        print(json.dumps({'state':'blocked','reason':'output_must_be_new_and_local'}))
        return 2
    codex = shutil.which('codex')
    powershell = str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
    if not codex or not Path(powershell).is_file():
        print(json.dumps({'state':'blocked','reason':'probe_dependencies_missing'}))
        return 2
    result = run_probe(target,codex=codex,powershell=powershell)
    print(json.dumps(result))
    return 0 if result['result'] != 'INCONCLUSIVE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
