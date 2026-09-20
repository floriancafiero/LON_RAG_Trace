# Venue-Adaptive Research Factory

This directory now contains two workflows:

- `general_factory.py`: the reusable workflow for computational social science, NLP/TAL, digital humanities, historical NLP, computational literary studies, IR/RAG, and mixed projects.
- `trace_factory.py`: the earlier TRACE/League-of-Nations-specific workflow, kept for compatibility.

The generic factory is based on the same broad multi-agent principles as Engzell & Wilmers' *Paper Factory*: narrow fresh-context agents, parallel research packages, adversarial review, hard gates, explicit evidence ledgers, and late audits. The important change is that the workflow is **adapted per project and per target venue** instead of hard-coding one research style.

## What adapts

Each project provides an idea, data/material, and a target venue. The factory then:

1. profiles the project and inferred subfield;
2. searches recent works published in the target venue through OpenAlex;
3. ranks them by topical proximity to the project;
4. builds a local `venue_profile` from the nearest examples;
5. loads one or more discipline packs;
6. synthesizes a project-specific `research_contract`;
7. uses that contract to design 4–8 research streams;
8. selects one validated package as the paper backbone;
9. runs a venue-aware gap analysis to decide which extensions are actually worth doing;
10. proposes three paper architectures and reviews each from methods, field, and venue perspectives;
11. drafts only after evidence/support/dropped-findings audits;
12. runs number, claim, citation, venue-fit, and style audits before human review.

The accepted/published papers are used to infer **conventions and evidentiary expectations**, never to copy wording. Common patterns in the sample are not treated as formal venue requirements.

## Quick start

```bash
export OPENROUTER_API_KEY=...

python research_factory/general_factory.py init runs/my_paper \
  --question "My research question" \
  --field "computational social science" \
  --subfield "political communication" \
  --venue "New Media & Society" \
  --data path/to/data \
  --backend openrouter

python research_factory/general_factory.py run runs/my_paper
python research_factory/general_factory.py status runs/my_paper
```

DeepSeek through OpenRouter is the default model backend. `factory.json` stores the backend/model settings, and `--model` can override them at run time.

## Discipline packs

```bash
python research_factory/general_factory.py packs
```

Current packs:

- `nlp`
- `computational_social_science`
- `digital_humanities`
- `historical_nlp`
- `computational_literary_studies`
- `information_retrieval`

They are composable. For example:

```bash
python research_factory/general_factory.py init runs/stylometry \
  --question "..." \
  --field "NLP / computational literary studies" \
  --subfield "authorship representation learning" \
  --venue "EMNLP" \
  --pack nlp \
  --pack computational_literary_studies
```

If no pack is specified, the project profiler selects relevant packs from the field, subfield, and method family. A historical-RAG project can therefore combine NLP + information retrieval + digital humanities + historical NLP, while a survey paper can use computational social science without inheriting irrelevant benchmark conventions.

## Venue scout

The generic factory resolves the venue via OpenAlex, collects recent works published in that source, and ranks them against the project question/keywords. It writes:

```text
venue/scout_results.jsonl
venue/scout_summary.json
venue/papers/*.txt
venue/venue_profile.json
venue/venue_profile.md
```

The default window is five years and the top 24 papers are retained. When only abstracts are available, the profile is explicitly based on abstracts and must remain cautious about section/style claims.

### Hand-pick the closest accepted papers

For small or poorly indexed subfields, local examples are better:

```bash
python research_factory/general_factory.py init runs/project \
  --question "..." \
  --venue "Computational Humanities Research" \
  --local-paper examples/accepted1.txt \
  --local-paper examples/accepted2.txt \
  --offline
```

The current compact implementation ingests local `.txt`/`.md` examples directly. PDFs can be converted to text beforehand. Without `--offline`, local examples augment the OpenAlex sample.

OpenAlex publication in the resolved source is used as a practical proxy for an accepted/published paper. Track/workshop distinctions can be imperfect, so for conference targeting it is worth adding hand-picked examples from the exact track when possible.

## Research contract

After the venue profile and discipline packs are available, an agent writes:

```text
profiles/loaded_packs.md
profiles/loaded_packs.json
profiles/research_contract.md
profiles/research_contract.json
```

The contract classifies expectations as `REQUIRED`, `STRONGLY_EXPECTED`, `OPTIONAL`, or `NOT_APPLICABLE`. This is where the same engine becomes different workflows in practice: a CSS project emphasizes construct validity, sampling, effect sizes and identification; NLP emphasizes baselines, ablations, leakage and stochasticity; DH emphasizes corpus/source critique, interpretability and movement between aggregate patterns and cases.

## Venue-aware gap analysis

Extensions are deliberately **not fixed in advance**. After one findings package is selected, the factory asks what evidence is still missing for this exact paper given the local venue sample and the research contract. It writes:

```text
extensions/gap_analysis.md
extensions/extension_plan.json
```

Only extensions that can materially change confidence, interpretation, generalization, mechanism, or venue fit should be run.

## Retarget the same project

```bash
python research_factory/general_factory.py retarget runs/my_paper \
  --venue "TACL" \
  --track "article"

python research_factory/general_factory.py run runs/my_paper
```

Retargeting preserves the project files but resets workflow state so the venue profile, research planning, missing-evidence analysis, architecture, and draft can change. For expensive real projects, copying the run directory before retargeting is sensible if you want to preserve both trajectories.

## Smoke test

The `mock` backend exercises the whole orchestration without API calls or research claims:

```bash
python research_factory/general_factory.py init /tmp/factory_smoke \
  --question "A test question" \
  --field "digital humanities" \
  --subfield "historical NLP" \
  --venue "Mock Venue" \
  --backend mock --offline

python research_factory/general_factory.py run /tmp/factory_smoke --backend mock
```

A successful smoke run ends at `awaiting_human_review`.

## Important limits

A venue profile is a sample, not a rulebook, and the factory does not predict acceptance. OpenAlex source resolution can be imperfect. The quality of the adaptation improves substantially when the user supplies the exact track/article type and a few hand-picked close accepted papers. Human judgment remains the final gate for problem selection, contribution importance, and whether the paper should actually be submitted in its current form.
