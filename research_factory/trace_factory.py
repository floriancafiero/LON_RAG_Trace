#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures as cf, json, shutil, subprocess, time
from pathlib import Path
from prompts import P,FINDINGS,EXTENSIONS
from runtime import Config,Workspace,Task,make_backend

class Factory:
    def __init__(self,root,cfg):self.ws=Workspace(root.absolute());self.cfg=cfg;self.be=make_backend(cfg)
    def task(self,sid,t,force=False):
        if self.ws.done(sid) and not force:return
        ld=self.ws.root/'logs'/sid;ld.mkdir(parents=True,exist_ok=True);(ld/'prompt.txt').write_text(t.prompt);self.ws.event('agent_started',{'stage':sid,'name':t.name});start=time.time()
        try:
            res=self.be.run(t,self.ws.root);(ld/'response.txt').write_text(res or '');missing=[x for x in t.outputs if not (self.ws.root/x).exists()]
            if missing:raise RuntimeError(f'missing outputs {missing}')
            self.ws.mark(sid);self.ws.event('agent_finished',{'stage':sid,'seconds':time.time()-start})
        except Exception as e:(ld/'error.txt').write_text(repr(e));self.ws.update(status='failed',failed_stage=sid,error=str(e));raise
    def parallel(self,jobs):
        jobs=[j for j in jobs if not self.ws.done(j[0])]
        if not jobs:return
        with cf.ThreadPoolExecutor(max_workers=min(self.cfg.max_workers,len(jobs))) as ex:
            for f in cf.as_completed([ex.submit(self.task,*j) for j in jobs]):f.result()
    def gate(self,path,allowed):
        d=json.loads((self.ws.root/path).read_text());x=str(d['decision']).upper()
        if x not in allowed:raise RuntimeError(f'invalid gate {x}')
        return x
    def run(self):
        r=self.ws.root
        self.task('00_setup',Task('Project setup',P['setup'],['project_brief.md']))
        self.parallel([('01a_literature',Task('Early literature',P['literature'],['memos/literature_early.md','memos/citations_early.json'])),('01b_wrangle',Task('Benchmark wrangling',P['wrangle'],['memos/data_wrangler.md'])),('01c_context',Task('Benchmark context',P['context'],['memos/data_context.md']))])
        self.task('01d_schema',Task('Experimental schema',P['schema'],['analysis/variable_dictionary.md','memos/variables.md']));self.task('01e_viability',Task('Viability gate',P['viability'],['memos/viability_gate.json']))
        if self.gate('memos/viability_gate.json',{'PASS','KILL'})=='KILL':self.ws.update(status='killed');return 'killed'
        self.task('01f_descriptives',Task('Benchmark descriptives',P['descriptives'],['memos/descriptive_map.md']))
        self.parallel([(f'02a_findings_{i:02d}',Task(f'Findings stream {i}',P['finding']+f'\n\nASSIGNED: {FINDINGS[i]}\nWrite only in findings/stream_{i:02d}.',[f'findings/stream_{i:02d}/findings_memo.md',f'findings/stream_{i:02d}/run.sh'])) for i in range(1,7)])
        self.parallel([(f'02b_critic_{i:02d}',Task(f'Critic {i}',P['critic']+f'\nReview only findings/stream_{i:02d}.',[f'findings/stream_{i:02d}/critic.md'])) for i in range(1,7)]);self.parallel([(f'02c_revise_{i:02d}',Task(f'Revise {i}',P['revise']+f'\nRevise only findings/stream_{i:02d}.',[f'findings/stream_{i:02d}/resolution_ledger.md'])) for i in range(1,7)]);self.parallel([(f'02d_validate_{i:02d}',Task(f'Validate {i}',P['validate']+f'\nValidate only findings/stream_{i:02d}.',[f'findings/stream_{i:02d}/validation.json'])) for i in range(1,7)])
        self.task('03_select',Task('Findings selection',P['select'],['memos/findings_selection.json','findings_brief.md']))
        self.parallel([(f'04a_ext_{n}',Task('Extension '+n,p+f'\nWrite only in extensions/{n}.',[f'extensions/{n}/memo.md'])) for n,p in EXTENSIONS.items()]);self.parallel([(f'04b_arch_{i:02d}',Task(f'Architecture {i}',P['architect']+f'\nWrite architecture/map_{i:02d}/paper_map.md.',[f'architecture/map_{i:02d}/paper_map.md'])) for i in range(1,6)]);self.parallel([(f'04c_arch_review_{i:02d}',Task(f'Architecture review {i}',P['arch_review']+f'\nReview architecture/map_{i:02d}/paper_map.md.',[f'architecture/map_{i:02d}/review.md'])) for i in range(1,6)])
        self.task('04d_arch_decide',Task('Architecture decider',P['decide_arch'],['memos/proposal_decision.json','paper_map.md']));self.task('04e_proposal_audit',Task('Proposal audit',P['proposal_audit'],['audit_issue_ledger.md']));self.task('04f_unify',Task('Unified executor',P['unify'],['findings_brief.md','audit_issue_ledger.md']));self.ws.snapshot('pre_step5')
        self.task('05_data_audit',Task('Benchmark audit',P['data_audit'],['memos/data_audit.md','audit_issue_ledger.md']));self.task('06a_argument_research',Task('Focused related work',P['argument_research'],['memos/literature_argument.md','memos/citations_argument.json']));self.task('06b_methods_audit',Task('Methods audit',P['methods_audit'],['memos/methods_audit.md','audit_issue_ledger.md']))
        self.parallel([('07a_support',Task('Evidence support',P['support'],['sample_support.md'])),('07b_dropped',Task('Dropped findings',P['dropped'],['dropped_findings.md']))]);self.task('07c_draft',Task('Draft',P['draft'],['paper/paper.md','paper/paper.tex']));self.task('08_replication',Task('Replication gate',P['replication'],['memos/replication_gate.json']))
        if self.gate('memos/replication_gate.json',{'PASS','BLOCK'})=='BLOCK':self.ws.update(status='blocked_gate2');return 'blocked'
        self.task('09_review',Task('Constructive review',P['review'],['memos/constructive_review.md']));self.task('10_revision',Task('Revision',P['revision'],['memos/revision_resolution_ledger.md','paper/paper.md','paper/paper.tex']));self.task('11_claim_gate',Task('Claim gate',P['claim_gate'],['memos/claim_validity_gate.json']));g=self.gate('memos/claim_validity_gate.json',{'PASS','REOPEN','BLOCK'})
        if g=='REOPEN' and self.ws.state().get('gate3_reopens',0)<1:self.ws.update(gate3_reopens=1);self.task('10b_targeted_revision',Task('Targeted revision',P['revision']+'\nAddress only claim-gate targeted actions.',['memos/revision_resolution_ledger.md','paper/paper.md','paper/paper.tex']),True);self.task('11b_claim_gate',Task('Reopened claim gate',P['claim_gate'],['memos/claim_validity_gate.json']),True);g=self.gate('memos/claim_validity_gate.json',{'PASS','REOPEN','BLOCK'})
        if g!='PASS':self.ws.update(status='blocked_gate3');return 'blocked'
        self.task('12_citations',Task('Citation audit',P['citations'],['memos/citation_audit.md','paper/paper.tex']));self.task('13_format',Task('Formatting',P['format'],['memos/formatting_report.md','paper/paper.tex']));self.task('14_abstract',Task('Abstract',P['abstract'],['paper/abstract.txt','paper/paper.tex','paper/paper.md']));self.task('15_style',Task('Style',P['style'],['memos/style_report.md','paper/paper.tex','paper/paper.md']))
        pd=r/'paper';exe=shutil.which('latexmk');
        if exe:subprocess.run([exe,'-pdf','-interaction=nonstopmode','paper.tex'],cwd=pd,capture_output=True,text=True,timeout=300)
        if (pd/'paper.pdf').exists():shutil.copy2(pd/'paper.pdf',r/'papers'/'paper.pdf')
        self.ws.mark('16_delivery');self.ws.update(status='awaiting_human_review' if self.cfg.human_review else 'complete');(r/'human_review.md').write_text('# Human review\n\nAPPROVE / REVISE / REWIND\n') if self.cfg.human_review and not (r/'human_review.md').exists() else None;return self.ws.state()['status']

PLAN='''00 setup
01 benchmark/literature foundations + viability gate
02 six findings streams + critic/revision/validation
03 select exactly one package
04 JEV/model/budget/transfer/robustness/case/moonshot extensions + five architectures
05-06 data/method/literature audits
07 draft guardrails -> draft
08 replication gate
09-10 review/revision
11 claim-validity gate
12-15 citations/format/abstract/style
16 delivery + human review'''
def main():
    a=argparse.ArgumentParser();s=a.add_subparsers(dest='cmd',required=True);p=s.add_parser('init');p.add_argument('project');p.add_argument('--question');p.add_argument('--data',action='append',default=[]);p.add_argument('--backend',choices=['openrouter','command','mock'],default='openrouter');p.add_argument('--model');p=s.add_parser('run');p.add_argument('project');p.add_argument('--backend',choices=['openrouter','command','mock']);p.add_argument('--model');p=s.add_parser('status');p.add_argument('project');s.add_parser('plan');x=a.parse_args()
    if x.cmd=='init':
        r=Path(x.project);Workspace.create(r,x.question,[Path(v) for v in x.data]);c=Config();c.backend.kind=x.backend;c.backend.model=x.model or c.backend.model;c.save(r/'factory.json');print('Initialized',r);return
    if x.cmd=='run':
        r=Path(x.project).absolute();c=Config.load(r/'factory.json');c.backend.kind=x.backend or c.backend.kind;c.backend.model=x.model or c.backend.model;print(Factory(r,c).run());return
    if x.cmd=='status':print(json.dumps(Workspace(Path(x.project)).state(),indent=2));return
    print(PLAN)
if __name__=='__main__':main()
