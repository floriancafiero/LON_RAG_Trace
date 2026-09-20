# Research Factory

The repository now contains a general venue-adaptive Research Factory under [`research_factory/`](research_factory/README.md).

It supports computational social science, NLP/TAL, digital humanities, historical NLP, computational literary studies, IR/RAG, and mixed projects. The generic engine profiles the project, retrieves recent topically-near papers from the target venue (or accepts hand-picked local examples), builds a local venue profile, combines discipline-specific methodological packs, and adapts research streams, missing-evidence extensions, paper architecture, mock review, drafting, and audits to that project.

The earlier TRACE-specific workflow remains available as `research_factory/trace_factory.py`; the reusable engine is `research_factory/general_factory.py`.
