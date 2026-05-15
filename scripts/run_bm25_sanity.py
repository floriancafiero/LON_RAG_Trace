#!/usr/bin/env python3
"""
Run a lightweight BM25 sanity-check baseline on TRACE-formatted LoN inputs.

This is not the main TRACE evaluation. It is useful to verify that the corpus,
questions, and gold document IDs are aligned before launching TRACE-lite.
"""
import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


def tok(text):
    return re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)


def iter_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tok(d["text"]) for d in docs]
        self.doc_len = [len(t) for t in self.doc_tokens]
        self.avgdl = sum(self.doc_len) / max(len(self.doc_len), 1)
        df = Counter()
        for terms in self.doc_tokens:
            df.update(set(terms))
        n = len(docs)
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}
        self.tfs = [Counter(terms) for terms in self.doc_tokens]

    def score(self, query):
        qterms = tok(query)
        out = []
        for i, d in enumerate(self.docs):
            dl = self.doc_len[i] or 1
            score = 0.0
            tf = self.tfs[i]
            for term in qterms:
                if term not in tf:
                    continue
                denom = tf[term] + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += self.idf.get(term, 0.0) * tf[term] * (self.k1 + 1) / denom
            out.append((d["doc_id"], score))
        out.sort(key=lambda x: x[1], reverse=True)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--documents", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    docs = list(iter_jsonl(args.documents))
    questions = list(iter_jsonl(args.questions))
    bm25 = BM25(docs)

    rows = []
    by_split = defaultdict(list)

    for q in questions:
        ranked = bm25.score(q["question"])
        gold = q["gold_doc_ids"][0]
        rank = next((i + 1 for i, (doc_id, _) in enumerate(ranked) if doc_id == gold), None)
        rr = 0.0 if rank is None else 1.0 / rank
        split = q.get("metadata", {}).get("split", "")
        row = {
            "qid": q["qid"],
            "split": split,
            "gold_doc_id": gold,
            "bm25_rank": rank if rank is not None else "",
            "R1": int(rank == 1),
            "R3": int(rank is not None and rank <= 3),
            "R5": int(rank is not None and rank <= 5),
            "R10": int(rank is not None and rank <= 10),
            "MRR": rr,
        }
        rows.append(row)
        by_split[split].append(row)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def mean(rs, key):
        return sum(r[key] for r in rs) / len(rs)

    print("BM25 summary")
    for split, rs in sorted(by_split.items()):
        print(
            split,
            "N=", len(rs),
            "R@1=", round(mean(rs, "R1"), 3),
            "R@3=", round(mean(rs, "R3"), 3),
            "R@10=", round(mean(rs, "R10"), 3),
            "MRR=", round(mean(rs, "MRR"), 3),
        )


if __name__ == "__main__":
    main()
