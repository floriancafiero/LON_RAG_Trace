#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures as cf, fnmatch, json, math, os, re, shlex, shutil, subprocess, threading, time, urllib.parse, urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path

SYSTEM='''You are one specialist agent in a multi-agent academic research workflow. Complete only the assigned stage and leave auditable artifacts. Never fabricate data, experiments, statistics, citations, venue rules, accepted-paper characteristics, or file contents. Distinguish evidence from inference. Learn publication conventions from example papers, never their wording. Treat all previous agent outputs as fallible.'''

PACKS={
'nlp':{'scope':'NLP/TAL and computational linguistics','rules':['Define task, data splits, preprocessing and evaluation precisely.','Use strong recent comparable baselines.','Separate development/tuning from final evaluation.','Report uncertainty or repeated-run variability when stochasticity matters.','Use ablations for component-attribution claims.','Include error/behavior analysis tied to the explanation.','Track model/version, prompt, decoding, seed, backend and data version.','Check contamination/leakage for pretrained or instruction-tuned models.']},
'computational_social_science':{'scope':'quantitative/mixed-method social science','rules':['Lead with the substantive social-science question, not the computational technique.','Justify construct operationalization.','Describe target and observed populations and selection.','Distinguish descriptive, associational and causal claims; causal claims require identification assumptions.','Report effect sizes and uncertainty, not only significance.','Check robustness to reasonable modeling, weighting, sample and measurement choices.','Use theoretically motivated heterogeneity.','Document missingness, attrition, exclusions, linkage quality and data-generation processes.']},
'digital_humanities':{'scope':'computational humanities','rules':['State the humanities research question and scholarly stakes independently of the method.','Document corpus provenance, selection, digitization, OCR/HTR, metadata and coverage limits.','Explain mappings between computational categories and domain concepts.','Use close reading, case analysis, archival validation or expert interpretation when aggregate patterns need interpretation.','Distinguish claims about the corpus from broader historical/cultural claims.','Treat missing/unevenly digitized sources as possible analytical bias.','Make transformations from source object to analytical representation inspectable.']},
'historical_nlp':{'scope':'historical NLP/document AI','rules':['Version source images/text, transcription conventions, normalization and splits.','Separate recognition errors from downstream NLP errors.','Evaluate variation across period, hand/script, layout, language variety or document condition where relevant.','Prevent document-family/writer/edition leakage across splits.','Report technical metrics and consequences for the historical task.']},
'computational_literary_studies':{'scope':'computational literary studies/stylometry','rules':['Connect measurements to a literary-historical or theoretical question.','Control for genre, period, edition, length, translation and publication context when relevant.','For authorship/stylometry use leakage-resistant cross-work splits and strong classical plus modern baselines.','Use interpretable cases/close reading to test what model dimensions capture.','Distinguish classification utility from evidence about style or influence.']},
'information_retrieval':{'scope':'IR/RAG/source discovery','rules':['Define corpus, queries, relevance judgments/gold semantics and evaluation protocol precisely.','Compare strong lexical, dense and reranking baselines as appropriate.','Match/report compute and retrieval budgets for agentic/adaptive comparisons.','Report rank-sensitive metrics and accepted-set metrics when relevant.','Ablate retrieval channels, planning/agent steps, reranking and stopping/routing for component claims.','Measure latency/calls/tokens/cost for efficiency claims.','Prevent gold/evaluation-only metadata leakage into retrieval.']}
}

PROMPTS={
'profile':'Read checkpoint.md, project.json and input/data_manifest.json. Lightly inspect project materials. Write project_profile.json with research_question, field, subfield, paper_type, methods_family, data_types, claim_types, target_venue, track, ambition, keywords, nearest_subtopics, contribution_hypotheses, unknowns and confidence. Preserve user-supplied field/venue.',
'venue':'Read project_profile.json, venue/scout_results.jsonl, venue/scout_summary.json and any venue/papers/*.txt. Infer a LOCAL publication profile from the closest examples, not stereotypes. Write venue/venue_profile.md and venue/venue_profile.json with sample definition, years, contribution types, typical evidence, baselines/comparators, ablations/robustness, qualitative/human validation, dataset/corpus reporting, claim calibration, section architecture, appendix role, limitations/ethics/reproducibility and uncertainty. Observed patterns are not mandatory rules. Never imitate wording.',
'contract':'Read project_profile.json, venue/venue_profile.json and profiles/loaded_packs.md. Write profiles/research_contract.md and .json. For this project classify methodological obligations as REQUIRED, STRONGLY_EXPECTED, OPTIONAL or NOT_APPLICABLE, with rationale and source: discipline pack, venue sample, official rule or project logic. Explain conflicts between fields instead of averaging them.',
'viability':'Hard gate. Check whether the central contribution can realistically be supported for the target venue with available/obtainable evidence: novelty, data adequacy, benchmark/statistical power, baselines, identification where relevant, corpus provenance, reproducibility and cost/time blockers. Write memos/viability_gate.json with decision PASS, REFRAME or KILL, reason, headline_test, minimum_evidence, blocking_issues and venue_specific_risks. If KILL also write kill_memo.md.',
'plan':'Design 4-8 independent research streams tailored to this project, venue profile and research contract. Streams should address distinct evidentiary needs such as main effect/performance, identification, ablation, robustness, heterogeneity, qualitative/error analysis, transfer/external validity, efficiency or corpus validation. Write findings/stream_plan.json as a JSON list with id, name, question, why_it_matters and venue_expectation_addressed.',
'finding':'Pursue only the assigned stream. Produce ONE coherent candidate package with findings_memo.md and reproducible run.sh/scripts/logs. If it cannot be run, write a precise blocker/experiment plan and never invent results. State which venue/discipline expectation it addresses.',
'critic':'Adversarially review this findings package using the research contract and venue profile. Look for leakage, weak operationalization, confounding, unfair/outdated baselines, invalid metrics, missing uncertainty, tuning/cherry-picking, corpus bias, underpowered comparisons or inadequate qualitative validation. Write critic.md with BLOCKING/IMPORTANT/OPTIONAL issues tied to artifacts.',
'revise':'Revise the assigned package against critic.md; run new analysis when feasible. Write resolution_ledger.md mapping each issue to FIX, DOWNGRADE, DROP, NEW_ANALYSIS or NOT_APPLICABLE, with evidence paths. Preserve null/negative results.',
'validate':'Regenerate or trace core numbers/claims and check samples, metrics, uncertainty and comparator fairness. Write validation.json with decision VALIDATED or REJECTED, reason and blocking_issues.',
'select':'Choose exactly ONE validated package as the paper backbone using credibility, importance, interpretability, venue fit and coherence. Do not hybridize headline claims. Write memos/findings_selection.json and findings_brief.md.',
'gap':'Compare selected findings with venue profile and research contract. Identify what a well-informed reviewer would still reasonably ask for. Write extensions/gap_analysis.md and extensions/extension_plan.json as a list of at most five extensions with id, name, prompt, expected_information_gain, cost and stop_rule. Add only extensions that could change confidence, interpretation, generalization, mechanism or venue fit.',
'extension':'Execute/specify the assigned extension. Keep it subordinate to the main package. Write memo.md plus reproducible artifacts if runnable; state whether it changes, supports or weakens the headline claim.',
'architect':'Propose one disciplined paper map: one-sentence contribution, audience, introduction logic, literature positioning, section order, main-vs-appendix evidence and dropped material. Adapt to observed venue conventions without copying language.',
'methods_review':'Review the proposed map/evidence as a demanding methods/technical reviewer: inference/evaluation validity, robustness, uncertainty, reproducibility and evidence-claim fit. Write methods_review.md.',
'field_review':'Review as a subfield expert: importance, construct/corpus validity, nearby literature, substantive interpretation, alternatives and need for examples/qualitative evidence. Write field_review.md.',
'venue_review':'Review as someone familiar with the target venue, using venue_profile as empirical context rather than law. Focus on contribution shape, expected comparisons/evidence, presentation density and fit concerns. Label uncertain venue inferences. Write venue_review.md.',
'arch_decide':'Choose exactly one candidate architecture after all reviews; do not merge maps. Write memos/architecture_decision.json and paper_map.md, noting unresolved concerns.',
'audit':'Audit project before drafting against findings_brief, paper_map, research_contract and artifacts. Write audit_issue_ledger.md with severity, issue, affected claim, evidence path, required action and status. Use field-specific failure modes.',
'support':'Create evidence_support.md mapping every planned main claim to dataset/corpus/version, sample/documents, code/config, metric or interpretive procedure, uncertainty/validation and output path. Flag unsupported claims.',
'dropped':'Create dropped_findings.md listing analyses/claims/extensions that must not be headline evidence because rejected, exploratory, weak, tuned, redundant or out of scope.',
'draft':'Write paper/paper.md and compilable paper/paper.tex from the selected map and evidence. Follow broad target-venue structural conventions only where supported by venue sample/official rules. Every number must trace to artifacts. For DH/CSS, computational performance must not substitute for the substantive question; for NLP/IR, framing must not substitute for strong experiments.',
'number':'Trace every number, N, metric, table, figure and statistical statement to code/results. Check rounding, denominators, exclusions, splits, seeds and labels. Write memos/number_audit.json with decision PASS or BLOCK and issues.',
'claim':'Audit major claims and distinguish description, association, causality, benchmark improvement, mechanism, interpretation and generalization. Write memos/claim_validity_gate.json with decision PASS, REOPEN or BLOCK, blocking_issues and targeted_actions.',
'citation':'Verify citations and novelty/literature claims available in the project; remove/flag unverifiable references. Write memos/citation_audit.md.',
'venue_fit':'Compare the finished draft with venue_profile and official target constraints in the workspace. Write memos/venue_fit_report.md covering contribution shape, missing expected evidence, justified deviations, section balance, reproducibility/ethics/limitations and formatting. Do not predict acceptance.',
'style':'Edit for concise field-appropriate academic prose without changing science. Match broad register/information density, never phrasing from examples. Remove inflated claims, generic AI rhetoric and repetitive signposting. Write memos/style_report.md and update paper drafts.'
}

@dataclass
class BackendCfg:
    kind:str='openrouter';model:str='deepseek/deepseek-chat-v3.1';api_key_env:str='OPENROUTER_API_KEY';base_url:str='https://openrouter.ai/api/v1';temperature:float=.15;max_tokens:int=12000;max_tool_rounds:int=30;command_template:str|None=None
@dataclass
class Cfg:
    backend:BackendCfg=field(default_factory=BackendCfg);max_workers:int=6;timeout:int=1800;max_read_chars:int=160000;allow_shell:bool=True
    @classmethod
    def load(cls,p):
        if not p.exists():return cls()
        d=json.loads(p.read_text());b=BackendCfg(**d.pop('backend',{}));return cls(backend=b,**d)
    def save(self,p):p.write_text(json.dumps(asdict(self),indent=2))
@dataclass
class Task:name:str;prompt:str;outputs:list[str]

DIRS='input memos analysis outputs findings extensions architecture profiles venue venue/papers paper logs provenance archive'.split()
class WS:
    def __init__(self,root):self.root=Path(root).absolute();self.lock=threading.RLock()
    @classmethod
    def create(cls,root,question,data,project):
        w=cls(root);w.root.mkdir(parents=True,exist_ok=True)
        for d in DIRS:(w.root/d).mkdir(parents=True,exist_ok=True)
        (w.root/'project.json').write_text(json.dumps(project,indent=2,ensure_ascii=False))
        cp=w.root/'checkpoint.md'
        if not cp.exists():cp.write_text('# Research idea\n\n'+(question or 'Describe the project.')+'\n\n# Target\n\n'+str(project.get('target_venue','unknown'))+'\n')
        manifest=[]
        for i,p0 in enumerate(data or [],1):
            p=Path(p0).expanduser().absolute();t=w.root/'input'/f'data_{i:02d}_{p.name}'
            try:t.symlink_to(p,target_is_directory=p.is_dir());mode='symlink'
            except Exception:t.write_text(str(p));mode='pointer'
            manifest.append({'source':str(p),'mounted_as':str(t.relative_to(w.root)),'mode':mode})
        (w.root/'input'/'data_manifest.json').write_text(json.dumps(manifest,indent=2))
        if not (w.root/'state.json').exists():(w.root/'state.json').write_text(json.dumps({'completed':[],'status':'initialized','reopens':0},indent=2))
        return w
    def state(self):
        with self.lock:return json.loads((self.root/'state.json').read_text())
    def save_state(self,s):
        with self.lock:
            p=self.root/'state.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(s,indent=2));tmp.replace(p)
    def done(self,sid):return sid in self.state().get('completed',[])
    def mark(self,sid):
        with self.lock:
            s=self.state();
            if sid not in s['completed']:s['completed'].append(sid)
            s.update(status='running',last_stage=sid);self.save_state(s);self.event('stage_completed',{'stage':sid})
    def update(self,**kw):
        with self.lock:s=self.state();s.update(kw);self.save_state(s)
    def event(self,k,p):
        q=self.root/'provenance'/'events.jsonl';q.parent.mkdir(parents=True,exist_ok=True)
        with q.open('a') as f:f.write(json.dumps({'ts':time.time(),'kind':k,**p})+'\n')

class Tools:
    def __init__(self,root,cfg):self.root=Path(root).absolute();self.cfg=cfg
    def path(self,x):
        p=(self.root/x).absolute()
        if os.path.commonpath([str(p),str(self.root)])!=str(self.root):raise ValueError('path escape')
        return p
    def list_files(self,glob='**/*'):
        a=[]
        for p in self.root.rglob('*'):
            r=str(p.relative_to(self.root))
            if fnmatch.fnmatch(r,glob) and (p.is_file() or p.is_symlink()):a.append({'path':r})
            if len(a)>600:break
        return json.dumps(a)
    def read_file(self,path,start=0,max_chars=120000):return self.path(path).read_text(errors='replace')[start:start+min(max_chars,self.cfg.max_read_chars)]
    def write_file(self,path,content):p=self.path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content);return 'ok'
    def run_command(self,command):
        if not self.cfg.allow_shell:return 'ERROR shell disabled'
        if any(x in command.lower() for x in ['sudo ','rm -rf /','mkfs','shutdown','reboot','curl | sh','wget | sh']):return 'ERROR blocked'
        p=subprocess.run(command,cwd=self.root,shell=True,text=True,capture_output=True,timeout=self.cfg.timeout);return f'exit_code={p.returncode}\n'+((p.stdout or '')+('\nSTDERR:\n'+p.stderr if p.stderr else ''))[-60000:]
    def specs(self):
        def f(n,d,props,req=()):return {'type':'function','function':{'name':n,'description':d,'parameters':{'type':'object','properties':props,'required':list(req),'additionalProperties':False}}}
        return [f('list_files','List workspace files.',{'glob':{'type':'string'}}),f('read_file','Read file.',{'path':{'type':'string'},'start':{'type':'integer'},'max_chars':{'type':'integer'}},['path']),f('write_file','Write file.',{'path':{'type':'string'},'content':{'type':'string'}},['path','content']),f('run_command','Run shell command for reproducible analysis.',{'command':{'type':'string'}},['command'])]
    def call(self,n,a):
        try:return str(getattr(self,n)(**a))
        except Exception as e:return 'ERROR '+repr(e)
class Backend:
    def run(self,t,root):raise NotImplementedError
class OR(Backend):
    def __init__(self,cfg):self.cfg=cfg;self.key=os.getenv(cfg.backend.api_key_env);assert self.key,f'Missing {cfg.backend.api_key_env}'
    def run(self,t,root):
        tools=Tools(root,self.cfg);msgs=[{'role':'system','content':SYSTEM},{'role':'user','content':f'STAGE: {t.name}\n\n{t.prompt}\n\nRequired outputs:\n'+'\n'.join('- '+x for x in t.outputs)+'\nUse tools and verify outputs.'}]
        for _ in range(self.cfg.backend.max_tool_rounds):
            payload={'model':self.cfg.backend.model,'messages':msgs,'tools':tools.specs(),'tool_choice':'auto','temperature':self.cfg.backend.temperature,'max_tokens':self.cfg.backend.max_tokens};req=urllib.request.Request(self.cfg.backend.base_url.rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
            m=json.loads(urllib.request.urlopen(req,timeout=180).read())['choices'][0]['message'];msgs.append(m);calls=m.get('tool_calls') or []
            if not calls:return m.get('content') or ''
            for c in calls:
                try:a=json.loads(c['function'].get('arguments') or '{}');res=tools.call(c['function']['name'],a)
                except Exception as e:res='ERROR '+repr(e)
                msgs.append({'role':'tool','tool_call_id':c['id'],'content':res})
        return 'max tool rounds'
class Mock(Backend):
    def run(self,t,root):
        for rel in t.outputs:
            p=Path(root)/rel;p.parent.mkdir(parents=True,exist_ok=True)
            if rel.endswith('project_profile.json'):d={'research_question':'mock','field':'digital humanities','subfield':'historical NLP','paper_type':'research','methods_family':['retrieval'],'data_types':['text'],'claim_types':['benchmark'],'target_venue':'Mock Venue','track':'main','ambition':'solid','keywords':['historical','retrieval'],'nearest_subtopics':['historical NLP'],'contribution_hypotheses':['mock'],'unknowns':[],'confidence':1}
            elif rel.endswith('venue_profile.json'):d={'sample_n':0,'expected_evidence':['baselines','robustness'],'uncertainty':'mock'}
            elif rel.endswith('research_contract.json'):d={'obligations':[{'item':'reproducibility','level':'REQUIRED'}]}
            elif rel.endswith('viability_gate.json'):d={'decision':'PASS','blocking_issues':[]}
            elif rel.endswith('stream_plan.json'):d=[{'id':f'stream_{i:02d}','name':f'Stream {i}','question':'mock','why_it_matters':'mock','venue_expectation_addressed':'mock'} for i in range(1,5)]
            elif rel.endswith('validation.json'):d={'decision':'VALIDATED','blocking_issues':[]}
            elif rel.endswith('findings_selection.json'):d={'selected':'stream_01'}
            elif rel.endswith('extension_plan.json'):d=[{'id':'robustness','name':'Robustness','prompt':'robustness'}]
            elif rel.endswith('architecture_decision.json'):d={'selected':'map_01'}
            elif rel.endswith('number_audit.json'):d={'decision':'PASS','issues':[]}
            elif rel.endswith('claim_validity_gate.json'):d={'decision':'PASS','blocking_issues':[]}
            elif p.suffix=='.json':d={'status':'mock'}
            else:d=None
            if d is not None:p.write_text(json.dumps(d))
            elif p.suffix=='.tex':p.write_text('\\documentclass{article}\n\\begin{document}Mock\\end{document}')
            else:p.write_text('# '+t.name+'\n\nMock artifact.\n')
        return 'mock'
def backend(cfg):return OR(cfg) if cfg.backend.kind=='openrouter' else Mock()

def tok(s):return {x.lower() for x in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_'-]{3,}",s or '')}
def abstract(inv):
    if not inv:return ''
    a=[]
    for w,ps in inv.items():
        for p in ps:a.append((p,w))
    return ' '.join(w for _,w in sorted(a))
def sim(q,title,ab):
    q,d=tok(q),tok((title or '')+' '+(ab or ''))
    return (len(q&d)/max(1,len(q))) if q else 0
def getj(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ResearchFactory/0.4'});return json.loads(urllib.request.urlopen(req,timeout=60).read())

def _slug(s):
    return re.sub(r'[^A-Za-z0-9_-]+','_',s or 'paper')[:70]

def _extract_pdf(pdf,txt):
    """Best-effort PDF-to-text; returns True only when useful text was extracted."""
    try:
        exe=shutil.which('pdftotext')
        if exe:
            r=subprocess.run([exe,'-layout',str(pdf),str(txt)],capture_output=True,text=True,timeout=120)
            if r.returncode==0 and txt.exists() and txt.stat().st_size>1000:return True
    except Exception:pass
    try:
        from pypdf import PdfReader
        reader=PdfReader(str(pdf))
        text='\n\n'.join((p.extract_text() or '') for p in reader.pages)
        if len(text.strip())>1000:txt.write_text(text,errors='ignore');return True
    except Exception:pass
    return False

def _download_pdf(url,dst,max_bytes=30*1024*1024):
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 ResearchFactory/0.4','Accept':'application/pdf,*/*'})
        with urllib.request.urlopen(req,timeout=60) as r:
            data=r.read(max_bytes+1)
        if len(data)>max_bytes or not data.startswith(b'%PDF'):return False
        dst.write_bytes(data);return True
    except Exception:return False

def _source_score(requested,source):
    a=re.sub(r'\W+','',str(requested).lower());b=re.sub(r'\W+','',str(source.get('display_name','')).lower())
    if not a or not b:return 0
    if a==b:return 100
    if a in b or b in a:return 80
    return 10*len(tok(requested)&tok(source.get('display_name','')))

def scout(root,project):
    vd=root/'venue';pd=vd/'papers';pdfd=pd/'pdf';vd.mkdir(exist_ok=True);pd.mkdir(exist_ok=True);pdfd.mkdir(exist_ok=True)
    v=project.get('target_venue','unknown');q=' '.join(project.get('keywords') or []) or project.get('question','');out=[];resolved=None
    if not project.get('offline') and str(v).lower() not in {'unknown','auto','none',''}:
        srcs=getj('https://api.openalex.org/sources?'+urllib.parse.urlencode({'search':v,'per-page':10})).get('results') or []
        if srcs:
            src=max(srcs,key=lambda x:_source_score(v,x));resolved={'id':src.get('id'),'display_name':src.get('display_name'),'type':src.get('type')}
            sid=src['id'].split('/')[-1];year=time.gmtime().tm_year
            flt=f'primary_location.source.id:{sid},from_publication_date:{year-int(project.get("venue_years",5))+1}-01-01'
            url='https://api.openalex.org/works?'+urllib.parse.urlencode({'filter':flt,'per-page':100,'sort':'publication_date:desc','select':'id,doi,title,publication_year,primary_location,best_oa_location,abstract_inverted_index,cited_by_count'})
            for w in getj(url).get('results') or []:
                ab=abstract(w.get('abstract_inverted_index'));loc=w.get('best_oa_location') or w.get('primary_location') or {}
                out.append({'title':w.get('title'),'year':w.get('publication_year'),'doi':w.get('doi'),'abstract':ab,'pdf_url':loc.get('pdf_url'),'landing_page_url':loc.get('landing_page_url'),'topic_similarity':sim(q,w.get('title'),ab),'source':'openalex'})
    for p0 in project.get('local_papers') or []:
        p=Path(p0).expanduser().absolute()
        if p.exists():out.append({'title':p.stem,'year':None,'abstract':'','local_source':str(p),'topic_similarity':1.0,'source':'local'})
    out.sort(key=lambda x:x.get('topic_similarity',0),reverse=True);out=out[:int(project.get('venue_keep',24))]
    n_full=n_abstract=0
    with (vd/'scout_results.jsonl').open('w') as f:
        for i,r0 in enumerate(out,1):
            r=dict(r0);r['rank']=i
            if i<=int(project.get('venue_download_top',10)):
                stem=f'{i:02d}_{_slug(r.get("title"))}';txt=pd/(stem+'.txt')
                if r.get('local_source'):
                    src=Path(r['local_source'])
                    if src.suffix.lower() in {'.txt','.md'}:
                        txt.write_text(src.read_text(errors='replace'));r['extracted_text_path']=str(txt.relative_to(root));r['text_scope']='full_text';n_full+=1
                    elif src.suffix.lower()=='.pdf' and _extract_pdf(src,txt):
                        r['extracted_text_path']=str(txt.relative_to(root));r['text_scope']='full_text';n_full+=1
                elif r.get('pdf_url'):
                    pdf=pdfd/(stem+'.pdf')
                    if _download_pdf(r['pdf_url'],pdf) and _extract_pdf(pdf,txt):
                        r['pdf_path']=str(pdf.relative_to(root));r['extracted_text_path']=str(txt.relative_to(root));r['text_scope']='full_text';n_full+=1
                    elif pdf.exists():pdf.unlink()
                if not r.get('extracted_text_path') and r.get('abstract'):
                    txt.write_text((r.get('title') or '')+'\n\n'+r['abstract']);r['extracted_text_path']=str(txt.relative_to(root));r['text_scope']='abstract_only';n_abstract+=1
            f.write(json.dumps(r,ensure_ascii=False)+'\n')
    (vd/'scout_summary.json').write_text(json.dumps({'venue_requested':v,'venue_resolved':resolved,'query':q,'n_kept':len(out),'full_text_examples':n_full,'abstract_only_examples':n_abstract,'warning':'Publication in the resolved OpenAlex venue is a proxy for accepted/published work; conference track/workshop distinctions may require manual filtering. Full-text extraction is best-effort and falls back to abstracts.'},indent=2))

def choose_packs(profile,explicit):
    out=[]
    def add(x):
        if x in PACKS and x not in out:out.append(x)
    for x in explicit or []:add(x)
    b=(str(profile.get('field',''))+' '+str(profile.get('subfield',''))+' '+str(profile.get('methods_family',''))).lower()
    if any(x in b for x in ['nlp','language','stylometr','authorship','text classification']):add('nlp')
    if any(x in b for x in ['social science','sociolog','political','survey','econometr','causal','communication']):add('computational_social_science')
    if any(x in b for x in ['humanit','histor','literar','archive','cultural heritage','philolog']):add('digital_humanities')
    if any(x in b for x in ['historical nlp','ocr','htr','diachronic']):add('historical_nlp')
    if any(x in b for x in ['literar','stylometr','authorship']):add('computational_literary_studies')
    if any(x in b for x in ['retrieval','rag','search','ranking']):add('information_retrieval')
    if not out:add('nlp')
    return out

class Factory:
    def __init__(self,root,cfg):self.ws=WS(root);self.cfg=cfg;self.be=backend(cfg);self.project=json.loads((self.ws.root/'project.json').read_text())
    def task(self,sid,name,prompt,outputs,force=False):
        if self.ws.done(sid) and not force:return
        ld=self.ws.root/'logs'/sid;ld.mkdir(parents=True,exist_ok=True);(ld/'prompt.txt').write_text(prompt);start=time.time();self.ws.event('agent_started',{'stage':sid,'name':name})
        try:
            res=self.be.run(Task(name,prompt,outputs),self.ws.root);(ld/'response.txt').write_text(res or '');miss=[x for x in outputs if not (self.ws.root/x).exists()]
            if miss:raise RuntimeError(f'missing outputs {miss}')
            self.ws.mark(sid);self.ws.event('agent_finished',{'stage':sid,'seconds':time.time()-start})
        except Exception as e:self.ws.update(status='failed',failed_stage=sid,error=str(e));raise
    def parallel(self,jobs):
        jobs=[x for x in jobs if not self.ws.done(x[0])]
        if not jobs:return
        with cf.ThreadPoolExecutor(max_workers=min(self.cfg.max_workers,len(jobs))) as ex:
            for f in cf.as_completed([ex.submit(self.task,*j) for j in jobs]):f.result()
    def j(self,p,default):
        try:return json.loads((self.ws.root/p).read_text())
        except Exception:return default
    def gate(self,p,allowed):
        x=str(self.j(p,{}).get('decision','')).upper()
        if x not in allowed:raise RuntimeError(f'invalid gate {x}');return x
        return x
    def run(self):
        self.task('00_profile','Project profiler',PROMPTS['profile'],['project_profile.json'])
        if not self.ws.done('01_scout'):
            try:prof=self.j('project_profile.json',{});p={**self.project,**{k:v for k,v in prof.items() if v not in (None,'')}};scout(self.ws.root,p)
            except Exception as e:(self.ws.root/'venue'/'scout_results.jsonl').write_text('');(self.ws.root/'venue'/'scout_summary.json').write_text(json.dumps({'error':repr(e),'warning':'Venue discovery failed; venue inferences must remain uncertain.'}))
            self.ws.mark('01_scout')
        self.task('02_venue','Venue profiler',PROMPTS['venue'],['venue/venue_profile.md','venue/venue_profile.json'])
        if not self.ws.done('03_packs'):
            names=choose_packs(self.j('project_profile.json',{}),self.project.get('discipline_packs'));text='\n\n'.join('# '+PACKS[n]['scope']+'\n'+'\n'.join('- '+r for r in PACKS[n]['rules']) for n in names);(self.ws.root/'profiles'/'loaded_packs.md').write_text(text);(self.ws.root/'profiles'/'loaded_packs.json').write_text(json.dumps({'packs':names},indent=2));self.ws.mark('03_packs')
        self.task('04_contract','Discipline adapter',PROMPTS['contract'],['profiles/research_contract.md','profiles/research_contract.json'])
        self.task('05_viability','Viability gate',PROMPTS['viability'],['memos/viability_gate.json'])
        v=self.gate('memos/viability_gate.json',{'PASS','REFRAME','KILL'})
        if v=='KILL':self.ws.update(status='killed');return 'killed'
        self.task('06_plan','Research stream planner',PROMPTS['plan'],['findings/stream_plan.json']);streams=self.j('findings/stream_plan.json',[])
        if not isinstance(streams,list):streams=[]
        while len(streams)<4:
            i=len(streams)+1;streams.append({'id':f'stream_{i:02d}','name':f'Evidence stream {i}','question':'Address an unresolved evidentiary need.','venue_expectation_addressed':'research contract'})
        streams=streams[:8]
        self.parallel([(f'07a_{s.get("id",i)}',f"Findings {s.get('name',i)}",PROMPTS['finding']+'\n\nASSIGNED:\n'+json.dumps(s,indent=2)+f"\nWrite only findings/{s.get('id',i)}/.",[f"findings/{s.get('id',i)}/findings_memo.md",f"findings/{s.get('id',i)}/run.sh"]) for i,s in enumerate(streams,1)])
        self.parallel([(f'07b_{s.get("id",i)}','Critic',PROMPTS['critic']+f"\nReview only findings/{s.get('id',i)}/.",[f"findings/{s.get('id',i)}/critic.md"]) for i,s in enumerate(streams,1)])
        self.parallel([(f'07c_{s.get("id",i)}','Revision',PROMPTS['revise']+f"\nRevise only findings/{s.get('id',i)}/.",[f"findings/{s.get('id',i)}/resolution_ledger.md"]) for i,s in enumerate(streams,1)])
        self.parallel([(f'07d_{s.get("id",i)}','Validation',PROMPTS['validate']+f"\nValidate only findings/{s.get('id',i)}/.",[f"findings/{s.get('id',i)}/validation.json"]) for i,s in enumerate(streams,1)])
        self.task('08_select','Findings selector',PROMPTS['select'],['memos/findings_selection.json','findings_brief.md']);self.task('09_gap','Venue-aware gap analysis',PROMPTS['gap'],['extensions/gap_analysis.md','extensions/extension_plan.json']);ext=self.j('extensions/extension_plan.json',[]);ext=ext if isinstance(ext,list) else []
        self.parallel([(f'10_{e.get("id",i)}','Extension '+str(e.get('name',i)),PROMPTS['extension']+'\n\n'+json.dumps(e,indent=2)+f"\nWrite only extensions/{e.get('id',i)}/.",[f"extensions/{e.get('id',i)}/memo.md"]) for i,e in enumerate(ext[:5],1)])
        n=3;self.parallel([(f'11a_{i}','Architect',PROMPTS['architect']+f'\nWrite architecture/map_{i:02d}/paper_map.md.',[f'architecture/map_{i:02d}/paper_map.md']) for i in range(1,n+1)])
        reviews=[]
        for i in range(1,n+1):
            base=f'architecture/map_{i:02d}/paper_map.md';reviews += [(f'11b_m_{i}','Methods reviewer',PROMPTS['methods_review']+'\nReview '+base,[f'architecture/map_{i:02d}/methods_review.md']),(f'11b_f_{i}','Field reviewer',PROMPTS['field_review']+'\nReview '+base,[f'architecture/map_{i:02d}/field_review.md']),(f'11b_v_{i}','Venue reviewer',PROMPTS['venue_review']+'\nReview '+base,[f'architecture/map_{i:02d}/venue_review.md'])]
        self.parallel(reviews);self.task('12_arch','Architecture decider',PROMPTS['arch_decide'],['memos/architecture_decision.json','paper_map.md'])
        self.parallel([('13a','Scientific audit',PROMPTS['audit'],['audit_issue_ledger.md']),('13b','Evidence map',PROMPTS['support'],['evidence_support.md']),('13c','Dropped findings',PROMPTS['dropped'],['dropped_findings.md'])]);self.task('14_draft','Draft',PROMPTS['draft'],['paper/paper.md','paper/paper.tex']);self.task('15_num','Number audit',PROMPTS['number'],['memos/number_audit.json'])
        if self.gate('memos/number_audit.json',{'PASS','BLOCK'})=='BLOCK':self.ws.update(status='blocked_number_audit');return 'blocked_number_audit'
        self.task('16_claim','Claim gate',PROMPTS['claim'],['memos/claim_validity_gate.json']);c=self.gate('memos/claim_validity_gate.json',{'PASS','REOPEN','BLOCK'})
        if c!='PASS':self.ws.update(status='blocked_claim_gate');return 'blocked_claim_gate'
        self.parallel([('17a','Citation audit',PROMPTS['citation'],['memos/citation_audit.md']),('17b','Venue-fit audit',PROMPTS['venue_fit'],['memos/venue_fit_report.md'])]);self.task('18_style','Style pass',PROMPTS['style'],['memos/style_report.md','paper/paper.md','paper/paper.tex']);self.ws.update(status='awaiting_human_review');return 'awaiting_human_review'

def default_project(a):return {'question':a.question or 'Describe the project.','field':a.field,'subfield':a.subfield,'target_venue':a.venue,'track':a.track,'ambition':a.ambition,'discipline_packs':a.pack or [],'alternative_venues':[],'offline':a.offline,'local_papers':a.local_paper or [],'venue_years':a.venue_years,'venue_keep':a.venue_keep,'venue_download_top':a.venue_download_top}
def main():
    ap=argparse.ArgumentParser(description='Venue-adaptive multi-agent Research Factory');sp=ap.add_subparsers(dest='cmd',required=True)
    a=sp.add_parser('init');a.add_argument('root');a.add_argument('--question');a.add_argument('--field',default='auto');a.add_argument('--subfield',default='auto');a.add_argument('--venue',default='unknown');a.add_argument('--track',default='unknown');a.add_argument('--ambition',default='solid');a.add_argument('--pack',action='append',choices=sorted(PACKS));a.add_argument('--data',action='append',default=[]);a.add_argument('--local-paper',action='append',default=[]);a.add_argument('--offline',action='store_true');a.add_argument('--venue-years',type=int,default=5);a.add_argument('--venue-keep',type=int,default=24);a.add_argument('--venue-download-top',type=int,default=10);a.add_argument('--backend',choices=['openrouter','mock'],default='openrouter');a.add_argument('--model');a.add_argument('--max-workers',type=int,default=6)
    a=sp.add_parser('run');a.add_argument('root');a.add_argument('--backend',choices=['openrouter','mock']);a.add_argument('--model');a=sp.add_parser('status');a.add_argument('root');a=sp.add_parser('retarget');a.add_argument('root');a.add_argument('--venue',required=True);a.add_argument('--track');sp.add_parser('packs')
    x=ap.parse_args()
    if x.cmd=='packs':print('\n'.join(sorted(PACKS)));return
    if x.cmd=='init':
        p=default_project(x);w=WS.create(x.root,x.question,x.data,p);c=Cfg();c.backend.kind=x.backend;c.backend.model=x.model or c.backend.model;c.max_workers=x.max_workers;c.save(w.root/'factory.json');print(w.root);return
    root=Path(x.root).absolute()
    if x.cmd=='status':print(json.dumps(WS(root).state(),indent=2));return
    if x.cmd=='retarget':
        p=json.loads((root/'project.json').read_text());p['target_venue']=x.venue
        if x.track:p['track']=x.track
        (root/'project.json').write_text(json.dumps(p,indent=2));s=WS(root).state();s['completed']=[];s['status']='retargeted';WS(root).save_state(s);print('retargeted');return
    c=Cfg.load(root/'factory.json');
    if x.backend:c.backend.kind=x.backend
    if x.model:c.backend.model=x.model
    print(Factory(root,c).run())
if __name__=='__main__':main()
