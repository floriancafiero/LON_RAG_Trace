#!/usr/bin/env python3
"""
Prepare League of Nations Sampo inputs for TRACE / TRACE-lite.

This script converts:
  1. the speech-level corpus produced by scripts/build_lon_transfer.py
  2. one of the question JSONL files in data/semantic or data/simple

into a compact TRACE-friendly schema.
"""
import argparse
import json
from pathlib import Path


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def convert_document(row):
    return {
        "doc_id": row["doc_id"],
        "subcorpus": "lon_speeches",
        "title": f"{row.get('speaker', 'Unknown speaker')} ({row.get('year', '')})",
        "text": row.get("text", ""),
        "date": str(row.get("year", "")),
        "language": row.get("language", ""),
        "metadata": {
            "source_url": row.get("source_url", ""),
            "speaker": row.get("speaker", ""),
            "year": row.get("year", ""),
            "minute_id": row.get("minute_id", ""),
            "people_references": row.get("people_references", []),
            "place_references": row.get("place_references", []),
        },
    }


def convert_question(row, question_set):
    qlang = row.get("query_lang", row.get("query_language", ""))
    dlang = row.get("doc_lang", row.get("document_language", ""))
    return {
        "qid": row["qid"],
        "question": row["question"],
        "language": qlang,
        "question_set": question_set,
        "task_type": "singlehop_source_discovery",
        "target_subcorpus": "lon_speeches",
        "gold_doc_ids": [row["gold_doc_id"]],
        "metadata": {
            "split": row.get("split", f"{qlang}->{dlang}"),
            "query_language": qlang,
            "document_language": dlang,
            "source_url": row.get("source_url", row.get("gold_source_url", "")),
            "speaker": row.get("speaker", ""),
            "year": row.get("year", ""),
            "theme": row.get("theme", ""),
            "difficulty": row.get("difficulty", ""),
            "bm25_rank": row.get("bm25_rank", None),
            "gold_excerpt": row.get("gold_excerpt", ""),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", required=True, type=Path)
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--question-set", default="lon-semantic-100")
    args = parser.parse_args()

    docs = [convert_document(row) for row in iter_jsonl(args.documents)]
    questions = [convert_question(row, args.question_set) for row in iter_jsonl(args.questions)]

    write_jsonl(args.out / "trace_documents.jsonl", docs)
    write_jsonl(args.out / "trace_questions.jsonl", questions)

    manifest = {
        "n_documents": len(docs),
        "n_questions": len(questions),
        "question_set": args.question_set,
        "subcorpora": ["lon_speeches"],
        "notes": [
            "Use TRACE-lite: M_max=1, no replan, one target subcorpus.",
            "Gold labels are speech-level document IDs.",
            "The semantic question set is intended for transfer evaluation, not training.",
        ],
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
