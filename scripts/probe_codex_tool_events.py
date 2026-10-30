"""Probe Codex event visibility with a synthetic local Responses server.

No model, credentials, reference answers, or user data are used. The mock
requests a read of one synthetic file in a new workspace. Do not treat this
single command control as proof that all tool paths are reported.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llmagentbench.adapters import audit_codex_items
from llmagentbench.process import child_env

MARKER = 'SYNTHETIC_TOOL_EVENT_PROBE_64D8'


def classify(marker_seen: bool, audit_status: str, tool_output_present: bool) -> str:
    if not marker_seen or not tool_output_present:
        return 'INCONCLUSIVE'
    if audit_status == 'tool_event_reported':
        return 'TOOL_EVENT_DETECTED'
    return 'TOOL_EVENT_NOT_DETECTED'


def classify_disabled(marker_seen: bool, requests: int, tool_output_present: bool) -> str:
    if requests < 2 or not tool_output_present:
        return 'INCONCLUSIVE'
    if marker_seen:
        return 'COMMAND_READ_OBSERVED'
    return 'COMMAND_READ_NOT_OBSERVED'


def find_exec(tools: list, namespace: str | None = None):
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get('type') == 'namespace':
            found = find_exec(tool.get('tools', []), tool.get('name'))
            if found:
                return found
        elif tool.get('name') in {'exec', 'exec_command'}:
            return tool['name'], namespace
    return None


def run_probe(output: Path, *, codex: str, commands_disabled: bool = False) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    home, workspace = output/'home', output/'workspace'
    home.mkdir()
    workspace.mkdir()
    (workspace/'sentinel.txt').write_text(MARKER,encoding='utf-8')
    state = {'requests':0, 'marker_seen':False, 'auth_header':False, 'tool_exposed':False,
             'tool_output_present':False}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, items):
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream')
            self.send_header('Connection','close')
            self.end_headers()
            response = {'id':'resp_probe','object':'response','status':'completed','output':items}
            events = [{'type':'response.created','response':{**response,'status':'in_progress','output':[]}}]
            for index,item in enumerate(items):
                events.extend([{'type':'response.output_item.added','output_index':index,'item':item},
                               {'type':'response.output_item.done','output_index':index,'item':item}])
            events.append({'type':'response.completed','response':response})
            for index,event in enumerate(events):
                event['sequence_number'] = index
                self.wfile.write(('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n').encode())

        def do_POST(self):
            if self.headers.get('Authorization'):
                state['auth_header'] = True
                self.send_error(403)
                return
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            state['requests'] += 1
            if state['requests'] == 1:
                exposed = list(body.get('tools', []))
                for item in body.get('input', []):
                    if isinstance(item,dict):
                        exposed.extend(item.get('tools', []))
                found = find_exec(exposed)
                if found is None:
                    self.send_error(400)
                    return
                name,namespace = found
                state['tool_exposed'] = True
                arguments = json.dumps({'cmd':'Get-Content -LiteralPath sentinel.txt','workdir':str(workspace),
                                        'yield_time_ms':1000,'max_output_tokens':200})
                if name == 'exec':
                    call = {'type':'custom_tool_call','id':'ctc_probe','call_id':'call_probe',
                            'name':'exec','input':'text(await tools.exec_command('+arguments+'));'}
                else:
                    call = {'type':'function_call','id':'fc_probe','call_id':'call_probe',
                            'name':'exec_command','arguments':arguments}
                if namespace:
                    call['namespace'] = namespace
                self.respond([call])
            elif state['requests'] == 2:
                outputs = [item for item in body.get('input', []) if isinstance(item,dict)
                           and item.get('type') in {'function_call_output','custom_tool_call_output'}
                           and item.get('call_id') == 'call_probe']
                state['tool_output_present'] = bool(outputs)
                state['marker_seen'] = MARKER in json.dumps(outputs)
                self.respond([{'type':'message','id':'msg_probe','role':'assistant','status':'completed',
                               'content':[{'type':'output_text','text':'SYNTHETIC_CONTROL_COMPLETE','annotations':[]}]}])
            else:
                self.send_error(400)

    server = http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    provider = ('{ name="Synthetic local probe", base_url="http://127.0.0.1:' + str(server.server_port)
                + '/v1", wire_api="responses", requires_openai_auth=false, supports_websockets=false, '
                  'request_max_retries=0, stream_max_retries=0 }')
    argv = [codex,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--json','--color','never',
            '--sandbox','read-only','--model','gpt-6-luna','--cd',str(workspace),
            '--disable','memories','--disable','apps','--disable','plugins','--disable','browser_use',
            '--disable','computer_use','--disable','view_image','--disable','skill_search',
            '--enable','skip_host_skill_discovery','--config','agents.enabled=false',
            '--config','memories.use_memories=false','--config','memories.generate_memories=false',
            '--config','project_doc_max_bytes=0','--config','windows.sandbox="unelevated"',
            '--config','model_provider="synthetic_probe"','--config','model_providers.synthetic_probe='+provider,'-']
    if commands_disabled:
        features = ('shell_tool','unified_exec','code_mode','code_mode_host','shell_snapshot')
        for feature in features:
            argv[-1:-1] = ['--disable',feature]
    env = child_env()
    env['CODEX_HOME'] = str(home)
    env['NO_PROXY'] = '127.0.0.1,localhost'
    for key in list(env):
        if key.upper() in {'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'}:
            del env[key]
    try:
        try:
            process = subprocess.run(argv,cwd=workspace,env=env,input='Synthetic command-event probe.',
                                     capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
            audit = audit_codex_items(process.stdout)
            code = process.returncode
        except (OSError,subprocess.TimeoutExpired):
            audit,code = {'status':'inconclusive'},None
    finally:
        server.shutdown()
        server.server_close()
    receipt = {'schema_version':1,'probe':'synthetic_local_command_event','model_call':False,
               'provider':'LOCAL_DETERMINISTIC_FIXTURE','requests':state['requests'],
               'commands_disabled_configured':commands_disabled,
               'codex_executable_sha256':hashlib.sha256(Path(codex).read_bytes()).hexdigest(),
               'tool_exposed':state['tool_exposed'],'tool_output_present':state['tool_output_present'],
               'auth_header_present':state['auth_header'],
               'sentinel_read_confirmed':state['marker_seen'],'exit_code':code,'audit':audit,
               'result':(classify_disabled(state['marker_seen'],state['requests'],state['tool_output_present'])
                         if commands_disabled else classify(state['marker_seen'],audit['status'],
                                                            state['tool_output_present'])),
               'boundary':'One synthetic tool path only; other nested calls may be omitted.'}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--commands-disabled',action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = args.out.resolve()
    codex = shutil.which('codex')
    if (sys.platform != 'win32' or not target.is_relative_to((root/'.bench-runs').resolve())
            or target.exists() or not codex):
        print(json.dumps({'state':'blocked'}))
        return 2
    result = run_probe(target,codex=codex,commands_disabled=args.commands_disabled)
    print(json.dumps(result))
    return 0 if result['result'] != 'INCONCLUSIVE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
