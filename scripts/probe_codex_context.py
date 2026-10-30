"""Inspect synthetic Codex instruction discovery without calling a model."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from llmagentbench.process import child_env

GLOBAL_MARKER = 'SYNTHETIC_BENCH_GLOBAL_INSTRUCTION_61C4'
PROJECT_MARKER = 'SYNTHETIC_BENCH_PROJECT_INSTRUCTION_84A7'


def classify(high: dict, zero: dict) -> str:
    if high != {'global':True,'project':True} or not all(isinstance(zero.get(k),bool) for k in ('global','project')):
        return 'INCONCLUSIVE'
    if zero == {'global':True,'project':False}:
        return 'GLOBAL_NOT_CAPPED'
    if zero == {'global':False,'project':False}:
        return 'BOTH_NOT_VISIBLE'
    return 'OTHER'


def run_probe(output: Path, *, codex: str, runner=subprocess.run) -> dict:
    output.mkdir(parents=True,exist_ok=False)
    home,workspace = output / 'synthetic-home',output / 'workspace'
    home.mkdir()
    workspace.mkdir()
    (home / 'AGENTS.md').write_text(GLOBAL_MARKER+'\n',encoding='utf-8')
    (workspace / 'AGENTS.md').write_text(PROJECT_MARKER+'\n',encoding='utf-8')
    (workspace / 'BENCH_ROOT').write_text('',encoding='utf-8')
    environment = child_env()
    environment['CODEX_HOME'] = str(home)
    def inspect(budget):
        argv = [codex,'debug','prompt-input','--disable','memories',
                '-c','memories.use_memories=false','-c','memories.generate_memories=false',
                '-c','project_root_markers=["BENCH_ROOT"]','-c',f'project_doc_max_bytes={budget}',
                'Synthetic context probe.']
        try:
            result = runner(argv,cwd=workspace,env=environment,capture_output=True,text=True,
                            encoding='utf-8',errors='replace',timeout=25)
            if result.returncode != 0:
                return {}
            parsed = json.loads(result.stdout)
            if not isinstance(parsed,list):
                return {}
            return {'global':GLOBAL_MARKER in result.stdout,'project':PROJECT_MARKER in result.stdout}
        except (OSError,ValueError,subprocess.TimeoutExpired):
            return {}
    high,zero = inspect(32000),inspect(0)
    result = {'schema_version':1,'probe':'synthetic_instruction_discovery','model_call':False,
              'high_budget':high,'zero_budget':zero,'result':classify(high,zero),
              'boundary':'Synthetic debug input only; historical model inputs are not recoverable from this probe.'}
    (output / 'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True,help='New path under this repository .bench-runs/')
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    target = args.out.resolve()
    if not target.is_relative_to((repository / '.bench-runs').resolve()) or target.exists():
        print(json.dumps({'state':'blocked','reason':'output_must_be_new_and_local'}))
        return 2
    codex = shutil.which('codex')
    if not codex:
        print(json.dumps({'state':'blocked','reason':'codex_not_found'}))
        return 2
    result = run_probe(target,codex=codex)
    print(json.dumps(result))
    return 0 if result['result'] != 'INCONCLUSIVE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
