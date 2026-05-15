# Running TRACE-lite on the League of Nations Sampo transfer set

This repository contains the data preparation and evaluation inputs for a small League of Nations Sampo transfer case for TRACE.

The goal is **not** to train a model. The goal is to test whether TRACE can be reused on another historical archive as a bilingual, single-hop source discovery task.

## Recommended TRACE-lite configuration

Use the standard TRACE pipeline, but disable multi-hop machinery:

```yaml
task_name: lon_semantic_transfer
subcorpora:
  - lon_speeches

planner:
  enabled: true
  max_subquestions: 1
  force_single_subcorpus: lon_speeches

replan:
  enabled: false

retrieval:
  channels:
    - bm25
    - dense
    - exact
  temporal:
    enabled: true   # optional; year metadata is available
  rrf_k: 60
  candidate_cap_per_channel: 50

agent:
  max_steps: 4
  review_batch_size: 3
  verdicts: [accept, reject, hold]
  require_json: true
  pass_original_question: true
  pass_subquestion: true

rerank:
  count_grouped: true
```

If the local model is fragile, use smaller review batches (`2` or `3`) and a larger review generation budget. The previous local tests showed that verbose review outputs can break JSON parsing when the model is token-limited.

## Input files

After running `prepare_trace_inputs.py`, TRACE should consume:

- `data/trace_inputs/trace_documents.jsonl`
- `data/trace_inputs/trace_questions.jsonl`

Each question has one gold speech-level document:

```json
{
  "qid": "lon_sem_0001",
  "question": "...",
  "target_subcorpus": "lon_speeches",
  "gold_doc_ids": ["s1928003392_en"]
}
```

Each document has:

```json
{
  "doc_id": "s1928003392_en",
  "subcorpus": "lon_speeches",
  "title": "Speaker (year)",
  "text": "...",
  "date": "1928",
  "language": "en",
  "metadata": {"source_url": "..."}
}
```

## Metrics to report

For this transfer case, report single-hop metrics:

- R@1, R@3, R@5
- MRR
- accepted-set precision and recall (`P_acc`, `R_acc`)
- mean accepted documents (`#RET`)
- latency per question
- JSON validity / parse-error rate if testing local models

R@10 can be reported as a secondary metric, but R@1 and R@3 are more informative because each question has a single gold speech.
