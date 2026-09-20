from __future__ import annotations
import concurrent.futures as cf, fnmatch, json, os, shlex, shutil, subprocess, threading, time, urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable
from prompts import DEFAULT_CHECKPOINT, SYSTEM

@dataclass
class BackendConfig:
    kind: str='openrouter'; model: str='deepseek/deepseek-chat-v3.1'; api_key_env: str='OPENROUTER_API_KEY'; base_url: str='https://openrouter.ai/api/v1'; temperature: float=.15; max_tokens: int=12000; max_tool_rounds: int=30; command_template: str|None=None
@dataclass
class Config:
    backend: BackendConfig=field(default_factory=BackendConfig); max_workers:int=6; command_timeout_seconds:int=1800; max_read_chars:int=160000; human_review:bool=True; allow_shell:bool=True; strict_gates:bool=True
    @classmethod
    def load(cls,p:Path):
        if not p.exists(): return cls()
        d=json.loads(p.read_text()); b=BackendConfig(**d.pop('backend',{})); return cls(backend=b,**d)
    def save(self,p:Path): p.write_text(json.dumps(asdict(self),indent=2))

DIRS='input input/literature memos analysis analysis/code analysis/data outputs/tables outputs/figures findings extensions architecture paper logs provenance papers archive'.split()
@dataclass
class Workspace:
    root:Path; lock:threading.RLock=field(default_factory=threading.RLock,repr=False)
    @classmethod
    def create(cls,root:Path,question:str|None,data:Iterable[Path]):
        root=root.expanduser().absolute(); root.mkdir(parents=True,exist_ok=True)
        for d in DIRS:(root/d).mkdir(parents=True,exist_ok=True)
        cp=root/'checkpoint.md'
        if not cp.exists():
            text=DEFAULT_CHECKPOINT
            if question: text=text.replace("When does TRACE's agentic retrieval loop improve historical source discovery over simpler retrieval pipelines, and at what quality/cost trade-off? On the League of Nations bilingual transfer benchmark, identify which components create the gain and whether an adaptive JEV-style controller could improve continue/stop/escalate decisions without sacrificing retrieval quality.",question.strip())
            cp.write_text(text)
        manifest=[]
        for i,p0 in enumerate(data,1):
            p=p0.expanduser().absolute(); t=root/'input'/f'data_{i:02d}_{p.name}'
            if t.exists() or t.is_symlink(): shutil.rmtree(t) if t.is_dir() and not t.is_symlink() else t.unlink()
            try:t.symlink_to(p,target_is_directory=p.is_dir()); mode='symlink'
            except OSError:t.write_text(str(p)); mode='pointer'
            manifest.append({'source':str(p),'mounted_as':str(t.relative_to(root)),'mode':mode})
        (root/'input'/'data_manifest.json').write_text(json.dumps(manifest,indent=2))
        if not (root/'state.json').exists():(root/'state.json').write_text(json.dumps({'completed':[],'status':'initialized','gate3_reopens':0},indent=2))
        w=cls(root); w.event('project_created',{'data':manifest}); return w
    def state(self):
        with self.lock:
            p=self.root/'state.json'; return json.loads(p.read_text()) if p.exists() else {'completed':[],'status':'initialized','gate3_reopens':0}
    def update(self,**kw):
        with self.lock:s=self.state();s.update(kw);(self.root/'state.json').write_text(json.dumps(s,indent=2));return s
    def done(self,sid):return sid in self.state().get('completed',[])
    def mark(self,sid):
        with self.lock:
            s=self.state();
            if sid not in s['completed']:s['completed'].append(sid)
            s.update(last_stage=sid,status='running');(self.root/'state.json').write_text(json.dumps(s,indent=2));self.event('stage_completed',{'stage':sid})
    def event(self,k,payload):
        with self.lock:
            with (self.root/'provenance'/'events.jsonl').open('a') as f:f.write(json.dumps({'ts':time.time(),'kind':k,**payload})+'\n')
    def snapshot(self,label):
        dst=self.root/'archive'/label
        if dst.exists():shutil.rmtree(dst)
        dst.mkdir(parents=True)
        for rel in ['analysis','outputs','memos','paper','findings_brief.md','audit_issue_ledger.md']:
            src=self.root/rel
            if not src.exists():continue
            out=dst/rel
            if src.is_dir():shutil.copytree(src,out,dirs_exist_ok=True)
            else:out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)

class Tools:
    def __init__(self,root,cfg):self.root=root.absolute();self.cfg=cfg
    def path(self,rel):
        p=(self.root/rel).absolute()
        if os.path.commonpath([str(p),str(self.root)])!=str(self.root):raise ValueError('path escape')
        return p
    def list_files(self,glob='**/*'):
        out=[]
        for p in self.root.rglob('*'):
            rel=str(p.relative_to(self.root))
            if fnmatch.fnmatch(rel,glob) and (p.is_file() or p.is_symlink()):out.append({'path':rel,'size':p.stat().st_size if p.exists() else None})
            if len(out)>=500:break
        return json.dumps(out)
    def read_file(self,path,start=0,max_chars=None):return self.path(path).read_text(errors='replace')[start:start+min(max_chars or self.cfg.max_read_chars,self.cfg.max_read_chars)]
    def write_file(self,path,content):p=self.path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content);return f'wrote {path}'
    def run_command(self,command):
        if not self.cfg.allow_shell:return 'ERROR: shell disabled'
        if any(x in command.lower() for x in ['sudo ','rm -rf /','mkfs','shutdown','reboot','curl | sh','wget | sh']):return 'ERROR: command blocked'
        p=subprocess.run(command,cwd=self.root,shell=True,text=True,capture_output=True,timeout=self.cfg.command_timeout_seconds);return f'exit_code={p.returncode}\n'+((p.stdout or '')+('\nSTDERR:\n'+p.stderr if p.stderr else ''))[-60000:]
    def specs(self):
        def f(n,d,p,r=()):return {'type':'function','function':{'name':n,'description':d,'parameters':{'type':'object','properties':p,'required':list(r),'additionalProperties':False}}}
        return [f('list_files','List workspace files.',{'glob':{'type':'string'}}),f('read_file','Read UTF-8 file.',{'path':{'type':'string'},'start':{'type':'integer'},'max_chars':{'type':'integer'}},['path']),f('write_file','Write UTF-8 file.',{'path':{'type':'string'},'content':{'type':'string'}},['path','content']),f('run_command','Run shell command; save reproducible scripts/logs.',{'command':{'type':'string'}},['command'])]
    def call(self,n,a):
        try:return str(getattr(self,n)(**a))
        except Exception as e:return f'ERROR: {type(e).__name__}: {e}'

@dataclass
class Task:name:str;prompt:str;outputs:list[str]
class Backend:
    def run(self,t,root):raise NotImplementedError
class OpenRouter(Backend):
    def __init__(self,cfg):self.cfg=cfg;self.key=os.getenv(cfg.backend.api_key_env);assert self.key,f'Missing {cfg.backend.api_key_env}'
    def run(self,t,root):
        tools=Tools(root,self.cfg); user=f'STAGE: {t.name}\n\n{t.prompt}\n\nRequired outputs:\n'+"\n".join('- '+x for x in t.outputs)+'\nUse tools; verify outputs before finishing. If blocked, still write artifacts describing the blocker.'; msgs=[{'role':'system','content':SYSTEM},{'role':'user','content':user}]
        for _ in range(self.cfg.backend.max_tool_rounds):
            payload={'model':self.cfg.backend.model,'messages':msgs,'tools':tools.specs(),'tool_choice':'auto','temperature':self.cfg.backend.temperature,'max_tokens':self.cfg.backend.max_tokens};req=urllib.request.Request(self.cfg.backend.base_url.rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'});m=json.loads(urllib.request.urlopen(req,timeout=180).read())['choices'][0]['message'];msgs.append(m);calls=m.get('tool_calls') or []
            if not calls:return m.get('content') or ''
            for c in calls:
                try:a=json.loads(c['function'].get('arguments') or '{}');res=tools.call(c['function']['name'],a)
                except Exception as e:res=f'ERROR: {e}'
                msgs.append({'role':'tool','tool_call_id':c['id'],'content':res})
        return 'max tool rounds'
class Command(Backend):
    def __init__(self,cfg):self.cfg=cfg;assert cfg.backend.command_template
    def run(self,t,root):
        p=SYSTEM+'\n\n'+t.prompt+'\n\nRequired outputs:\n'+'\n'.join(t.outputs);cmd=self.cfg.backend.command_template.format(prompt=shlex.quote(p));r=subprocess.run(cmd,cwd=root,shell=True,text=True,capture_output=True,timeout=self.cfg.command_timeout_seconds);assert r.returncode==0,r.stderr[-4000:];return r.stdout
class Mock(Backend):
    def run(self,t,root):
        for rel in t.outputs:
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
            if p.suffix=='.json':
                d={'decision':'PASS','reason':'mock','blocking_issues':[]} if any(x in p.name for x in ['viability','replication','claim_validity']) else ({'selected':'stream_01','reason':'mock'} if 'selection' in p.name else ({'selected':'map_01','reason':'mock'} if 'proposal_decision' in p.name else {'status':'mock'}));p.write_text(json.dumps(d))
            elif p.suffix=='.tex':p.write_text('\\documentclass{article}\n\\begin{document}Mock.\\end{document}')
            else:p.write_text('# '+t.name+'\n\nMock artifact.\n')
        return 'mock'
def make_backend(cfg):return {'openrouter':OpenRouter,'command':Command,'mock':lambda c:Mock()}[cfg.backend.kind](cfg)
