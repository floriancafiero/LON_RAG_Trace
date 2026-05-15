# LON_RAG_Trace

League of Nations Sampo transfer case for TRACE / TRACE-lite.

This repository prepares a small bilingual source-discovery evaluation from the League of Nations Sampo / Minutes of Multilateralism data. It is intended as a second application case for TRACE beyond HistoriQA-ThirdRepublic.

## Repository contents

- `scripts/build_lon_transfer.py`  
  Builds a speech-level retrieval corpus and two question sets from the Zenodo dump `minutes-data-v1.1.0.zip`.

- `scripts/prepare_trace_inputs.py`  
  Converts the LoN corpus and questions into a TRACE-friendly JSONL schema.

- `scripts/run_bm25_sanity.py`  
  Runs a quick BM25 baseline to verify that document IDs and gold labels align.

- `configs/trace_lite_lon.yaml`  
  Suggested TRACE-lite configuration for the transfer case.

- `docs/TRACE_LITE_INTEGRATION.md`  
  Notes for plugging the generated files into TRACE / TRACE-lite.

The generated corpora and question files are not committed by default because they are reproducible from the Zenodo dump and can be regenerated locally.

## Data source

The raw data are not committed here because the Zenodo dump is large. Download `minutes-data-v1.1.0.zip` from the League of Nations Sampo / Minutes of Multilateralism Zenodo record and place it at:

```text
data/raw/minutes-data-v1.1.0.zip
```

## Quick start

```bash
git clone https://github.com/floriancafiero/LON_RAG_Trace.git
cd LON_RAG_Trace

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p data/raw outputs
# Put minutes-data-v1.1.0.zip in data/raw/

python scripts/build_lon_transfer.py \
  --zip data/raw/minutes-data-v1.1.0.zip \
  --out data/processed

python scripts/prepare_trace_inputs.py \
  --documents data/processed/lon_documents.jsonl \
  --questions data/processed/semantic/lon_semantic_questions_100.jsonl \
  --out data/trace_inputs \
  --question-set lon-semantic-100

python scripts/run_bm25_sanity.py \
  --documents data/trace_inputs/trace_documents.jsonl \
  --questions data/trace_inputs/trace_questions.jsonl \
  --out outputs/bm25_semantic_results.csv
```

Then run TRACE-lite on:

```text
data/trace_inputs/trace_documents.jsonl
data/trace_inputs/trace_questions.jsonl
```

Recommended TRACE-lite settings are documented in [`docs/TRACE_LITE_INTEGRATION.md`](docs/TRACE_LITE_INTEGRATION.md), with a YAML template in [`configs/trace_lite_lon.yaml`](configs/trace_lite_lon.yaml).

## Generated question sets

### Semantic set

Generated at:

```text
data/processed/semantic/lon_semantic_questions_100.jsonl
data/processed/semantic/lon_semantic_questions_review.csv
data/processed/semantic/bm25_semantic_summary.csv
```

This is the recommended set for the paper. Questions are phrased as historical source-discovery needs rather than direct speaker--year--entity lookups. They retain enough metadata to remain manually reviewable, but BM25 is much less dominant, especially in cross-lingual settings.

Balanced splits:

- 25 EN→EN
- 25 FR→FR
- 25 FR→EN
- 25 EN→FR

### Simple set

Generated at:

```text
data/processed/simple/lon_questions_200.jsonl
data/processed/simple/bm25_summary.csv
```

This set uses explicit speaker--year--entity combinations. It is useful for testing extraction and gold alignment, but it is too easy to be the main transfer evaluation.

## Suggested framing for the CIKM draft

Use the semantic set as a lightweight transfer case:

> To assess whether TRACE can be reused beyond HistoriQA-ThirdRepublic, we evaluate a single-hop bilingual source-discovery setting on League of Nations Sampo. This tests integration with a public LOD-based historical archive rather than a project-specific document store.

## Repository status

This repository contains reproducible data-preparation scripts and TRACE-lite integration documentation. It does not contain the full raw Zenodo dump or a copy of TRACE itself.
