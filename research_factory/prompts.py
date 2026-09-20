DEFAULT_CHECKPOINT = '''# Research question

When does TRACE's agentic retrieval loop improve historical source discovery over simpler retrieval pipelines, and at what quality/cost trade-off? On the League of Nations bilingual transfer benchmark, identify which components create the gain and whether an adaptive JEV-style controller could improve continue/stop/escalate decisions without sacrificing retrieval quality.

# Benchmark
Use the repository's LoN semantic transfer set (100 questions; EN→EN, FR→FR, EN→FR, FR→EN; one gold speech per question). Treat repository scripts/configs as evidence; do not assume uncommitted TRACE results exist.

# Required comparisons
BM25; matched-budget non-agentic fused retrieval where available; TRACE-lite; retrieval/agent-step ablations; all four language directions. Primary metrics: R@1, R@3, R@5, MRR. Also accepted-set precision/recall, accepted-set size, latency, calls/tokens/cost when available.

# JEV
JEV is an extension, not an established result. If callable code/model exists, test it as a controller for continue/stop/escalate or retrieval granularity under matched compute. Otherwise write an implementation/experiment specification and do not invent results.

# Guardrails
Never expose gold IDs/excerpts/source URLs/evaluation-only metadata to retrieval agents. Do not tune on the final 100-question test set. Version model, prompt, seed, retrieval budget and benchmark. Count parse failures/dropped questions as failures unless a rule was fixed in advance. Preserve null/negative ablations.

# Audience
Information retrieval / NLP / digital archives. Make one clear, testable contribution.
'''

SYSTEM = '''You are one agent in a TRACE retrieval/RAG research workflow. Complete only the assigned stage and leave auditable artifacts. Never fabricate data, experiments, numbers, citations or file contents. Prefer reproducible scripts and exact run manifests. Never use gold/evaluation-only metadata inside retrieval decisions. Treat previous outputs as fallible. Write every required output before finishing.'''

P = {
'setup': 'Read checkpoint.md and input/data_manifest.json. Lightly inspect benchmark/config/run artifacts. Write project_brief.md with task, units, gold semantics, splits, available baselines, TRACE components, model/backend assumptions, metrics, audience, unknowns and plan.',
'literature': 'Build a pre-results literature map covering agentic/adaptive retrieval, stopping/routing, archival/historical RAG, multilingual retrieval, evaluation, and any controller named in checkpoint.md (including JEV). Verify identifiers. Write memos/literature_early.md and memos/citations_early.json.',
'wrangle': 'Audit documents/questions/gold IDs/splits/languages/source URLs/evaluation scripts/run outputs. Check duplicate IDs, absent golds, missing text, repeated questions, leakage fields, counts and split balance. Save checks under analysis/code/ and write memos/data_wrangler.md.',
'context': 'Explain benchmark provenance, correctness criteria, question generation, gold semantics, bilingual directions and inference-time vs evaluation-only metadata. Write memos/data_context.md with leakage risks.',
'schema': 'Define systems/configs, channels, planner/replan, max steps, model/backend, seeds, subsets, language directions, metrics and cost/latency/token accounting. Validate metrics on hand-checkable cases. Write analysis/variable_dictionary.md and memos/variables.md.',
'viability': 'Hard gate. Check benchmark difficulty, gold alignment, credible baseline, runnable TRACE/comparator, API/model access, metric correctness, split integrity, stochasticity and whether the contribution exceeds parameter tuning. Write memos/viability_gate.json with decision PASS or KILL, reason, headline_test, diagnostics, blocking_issues. If KILL also write kill_memo.md.',
'descriptives': 'Map corpus/question counts, lengths, language directions, BM25 difficulty/gold ranks where available, split balance, missing metadata and baseline performance. Save reproducible outputs and memos/descriptive_map.md.',
'finding': 'Pursue the assigned direction only in the assigned stream. Converge on ONE coherent empirical package. Name exact systems/configs, subset, metrics and uncertainty. No gold leakage or test tuning. Produce findings_memo.md, reproducible scripts/logs and run.sh; if code/credentials are unavailable, state the blocker and analyze only available artifacts.',
'critic': 'Adversarial IR/RAG review: test-set tuning, leakage, unfair budgets, incomparable models, metric/averaging bugs, missing uncertainty, cherry-picked splits, stochastic single runs, omitted cost, parse failures dropped, claim/table mismatch. Write critic.md with BLOCKING/IMPORTANT/OPTIONAL issues.',
'revise': 'Revise against critic.md and write resolution_ledger.md mapping each issue to FIX, DOWNGRADE, DROP or NOT_APPLICABLE with evidence. Keep null/negative results and exact configs.',
'validate': 'Regenerate or trace core numbers; verify fair budgets, metric semantics and claim calibration. Write validation.json with decision VALIDATED or REJECTED, blocking_issues and reason.',
'select': 'Choose exactly ONE validated stream based on credibility, importance, interpretability and coherence; never hybridize. Write memos/findings_selection.json and findings_brief.md with binding benchmark/config/metric definitions.',
'architect': 'Propose one disciplined paper map: problem, gap, one-sentence contribution, benchmark, systems, primary metrics, evidence sequence, main-vs-appendix extensions and dropped material.',
'arch_review': 'Review one paper map against empirical artifacts. Flag unsupported novelty, hidden benchmark choices, unfair baselines, mechanistic claims without ablations, metric inconsistencies or distracting extensions. Write review.md with PASS/REVISE.',
'decide_arch': 'Choose exactly one of five maps; do not merge. Write memos/proposal_decision.json and paper_map.md.',
'proposal_audit': 'Audit paper_map.md against findings_brief.md, code/logs, benchmark provenance and extensions. Write audit_issue_ledger.md with severity, claim, evidence path and required action.',
'unify': 'Build one unified experiment package around paper_map.md: benchmark version, subset, seeds, backend/model, budgets, configs, metrics, uncertainty, cost/latency and run manifests. Update findings_brief.md and audit_issue_ledger.md.',
'data_audit': 'Late benchmark audit: corpus/question/gold integrity, duplicates/leakage, generation provenance, split separation, inference metadata leakage, language split correctness, dropped questions, parse failures and reported N. Write memos/data_audit.md and update audit_issue_ledger.md.',
'argument_research': 'Focused related-work review around the settled contribution; verify nearest methods/benchmarks and novelty. Write memos/literature_argument.md and memos/citations_argument.json.',
'methods_audit': 'Audit metrics, paired uncertainty, stochastic runs/seeds, model/prompt versioning, matched compute, hyperparameter selection, fusion/reranking fairness, cost/latency, failures and reproducibility. Write memos/methods_audit.md and update audit_issue_ledger.md.',
'support': 'Create sample_support.md mapping every planned main result to subset, N, language split, configs, model/backend, seed/run count, metric, uncertainty and exact artifact path.',
'dropped': 'Create dropped_findings.md listing findings/configs that must not be headline evidence because rejected, exploratory, tuned, redundant or failed validation.',
'draft': 'Write paper/paper.md and compilable paper/paper.tex from the unified evidence. Every number must trace to artifacts; every systems claim must name its comparison; novelty must be verified. Be explicit about LoN transfer limits. Do not imply JEV results if only a design exists.',
'replication': 'Gate 2: trace every empirical claim/number/table/figure to scripts, configs, logs and results. Check N, metrics, rounding, splits, seeds and labels; fix simple mismatches. Write memos/replication_gate.json with decision PASS or BLOCK, reason, blocking_issues, checked_claims.',
'review': 'Review the whole draft like a demanding IR/NLP reviewer: contribution, benchmark validity, baseline fairness, ablations, uncertainty, efficiency, multilingual analysis, related work, reproducibility and transfer overclaiming. Write memos/constructive_review.md.',
'revision': 'Revise against constructive review/open audit issues. Write memos/revision_resolution_ledger.md mapping issues to FIX, DOWNGRADE, DROP, NEW_ANALYSIS or NOT_APPLICABLE. Update paper/paper.md and paper/paper.tex.',
'claim_gate': 'Gate 3: terms such as agentic, better, efficient, robust, multilingual and transfer must be justified by experiments actually run. Check blocking audit issues. Write memos/claim_validity_gate.json with decision PASS, REOPEN or BLOCK, reason, blocking_issues, targeted_actions.',
'citations': 'Verify every citation and related-work/novelty claim. Remove or flag unverifiable references; never guess. Write memos/citation_audit.md and update paper/paper.tex.',
'format': 'Standardize tables/figures: system names, metric definitions, N/split, uncertainty, cost/latency units and reproducible sources. Write memos/formatting_report.md and update paper/paper.tex.',
'abstract': 'Write paper/abstract.txt and update drafts with a concise abstract: problem, TRACE setting, LoN bilingual benchmark, principal comparison, only verified results and limitations.',
'style': 'Edit for concise natural academic prose without changing science. Remove inflated adjectives, generic LLM rhetoric and formulaic repetition. Write memos/style_report.md and update drafts.'
}

FINDINGS = {
1: 'Retrieval-channel baselines/ablations: BM25, dense, exact, temporal, fusion.',
2: 'Agentic contribution: retrieval-only/fixed-depth vs TRACE loop under matched compute.',
3: 'Bilingual transfer across EN→EN, FR→FR, EN→FR, FR→EN.',
4: 'Efficiency/stopping: steps, accepted set, calls/tokens/latency/cost vs quality.',
5: 'Error/calibration: failures, accept/reject/hold, rank movement, parse failures.',
6: 'Robustness/reproducibility: seeds, prompt/config/model perturbations, bootstrap uncertainty.'
}

EXTENSIONS = {
'jev_controller': 'If callable JEV is available, test it as a continue/stop/escalate or granularity controller against matched-compute fixed TRACE policies. Otherwise write a precise integration/experiment specification; never invent results.',
'model_sensitivity': 'Test/design sensitivity across available LLM backends/models while holding retrieval/evaluation fixed.',
'budget_ablation': 'Vary candidate caps, review batch, max steps or equivalent budget; build quality-vs-cost/latency curves.',
'cross_domain_transfer': 'Use available HistoriQA/other outputs if present; otherwise specify a preregisterable transfer experiment.',
'primary_robustness': 'Pressure-test seeds, prompts, cutoffs, bootstrap resamples, language mix and reasonable configs.',
'qualitative_cases': 'Trace a small transparent rule-based set of success/failure cases; do not use anecdotes as aggregate evidence.',
'moonshot': 'Pursue one ambitious testable extension such as adaptive routing across archives or predicting when agentic retrieval is worth its cost; failure is acceptable.'
}
