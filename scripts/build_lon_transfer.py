#!/usr/bin/env python3
"""
Build League of Nations Sampo transfer inputs for TRACE / TRACE-lite.

Input:
  data/raw/minutes-data-v1.1.0.zip

Outputs in the chosen --out directory:
  - lon_documents.jsonl                         speech-level corpus
  - semantic/lon_semantic_questions_100.jsonl   harder semantic questions
  - semantic/lon_semantic_questions_review.csv  manual review sheet
  - semantic/bm25_semantic_summary.csv          BM25 sanity-check summary
  - simple/lon_questions_200.jsonl              easier metadata questions
  - simple/bm25_summary.csv                     BM25 sanity-check summary

The semantic set is the recommended one for the paper. It is single-hop but is
phrased as historical source discovery rather than direct metadata lookup.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import pandas as pd

SEED = 42
BASE_URL = "https://minutes.ldf.fi"
random.seed(SEED)

THEMES = {
    "law_arbitration_international_order": {
        "keywords": ["arbitration", "court", "law", "legal", "juridical", "covenant", "treaty", "justice", "dispute", "droit", "juridique", "arbitrage", "cour", "traité", "justice", "différend"],
        "en": "turns diplomatic conflict into a matter of rules, procedure, and adjudication",
        "fr": "présente le conflit diplomatique comme une question de règles, de procédure et d'arbitrage",
    },
    "finance_economic_reconstruction": {
        "keywords": ["financial", "finance", "economic", "budget", "customs", "loan", "loans", "reconstruction", "currency", "financier", "finances", "économique", "budget", "douanes", "emprunt", "reconstruction", "monnaie"],
        "en": "links monetary stability and postwar recovery to the wider ordering of relations between states",
        "fr": "relie la stabilité monétaire et la reconstruction d'après-guerre à l'organisation des relations entre États",
    },
    "mandates_colonial_governance": {
        "keywords": ["mandate", "mandates", "colonial", "colony", "colonies", "native", "administration", "territory", "mandat", "mandats", "colonial", "colonie", "colonies", "indigène", "administration", "territoire"],
        "en": "frames colonial administration as an international responsibility rather than a purely national matter",
        "fr": "présente l'administration coloniale comme une responsabilité internationale plutôt que comme une affaire strictement nationale",
    },
    "health_epidemics": {
        "keywords": ["health", "hygiene", "epidemic", "disease", "sanitary", "medical", "santé", "hygiène", "épidémie", "maladie", "sanitaire", "médical"],
        "en": "treats public health as a problem requiring international coordination and shared expertise",
        "fr": "présente la santé publique comme un problème exigeant une coordination internationale et une expertise partagée",
    },
    "disarmament_security": {
        "keywords": ["disarmament", "armaments", "security", "military", "war", "peace", "forces", "désarmement", "armements", "sécurité", "militaire", "guerre", "paix", "forces"],
        "en": "presents the limitation of military power as a precondition for lasting peace",
        "fr": "présente la limitation de la puissance militaire comme une condition préalable à une paix durable",
    },
    "minorities_rights": {
        "keywords": ["minority", "minorities", "rights", "protection", "nationality", "religion", "minorité", "minorités", "droits", "protection", "nationalité", "religion"],
        "en": "frames minority protection as an international legal and political obligation",
        "fr": "présente la protection des minorités comme une obligation juridique et politique internationale",
    },
    "refugees_displacement": {
        "keywords": ["refugee", "refugees", "passport", "nansen", "emigration", "migration", "réfugié", "réfugiés", "passeport", "nansen", "émigration", "migration"],
        "en": "discusses displacement as a problem of international coordination rather than local relief alone",
        "fr": "présente le déplacement des populations comme un problème de coordination internationale plutôt que comme une simple assistance locale",
    },
    "opium_narcotics": {
        "keywords": ["opium", "narcotic", "drug", "traffic", "trafic", "stupéfiant", "drogue"],
        "en": "treats narcotics control as a transnational administrative and moral problem",
        "fr": "présente le contrôle des stupéfiants comme un problème transnational, administratif et moral",
    },
    "labour_social_policy": {
        "keywords": ["labour", "labor", "worker", "workers", "social", "employment", "travail", "ouvrier", "ouvriers", "social", "emploi", "chômage"],
        "en": "connects labour and social policy to international cooperation after the war",
        "fr": "relie le travail et la politique sociale à la coopération internationale d'après-guerre",
    },
}


def short_id(uri: str) -> str:
    if not isinstance(uri, str):
        return ""
    return uri.rstrip("/").split("/")[-1]


def clean_label(label: str) -> str:
    if not isinstance(label, str):
        return ""
    return re.sub(r"\s*\([^)]*\d{4}[^)]*\)\s*$", "", label).strip()


def lang_code(lang: str) -> str:
    value = str(lang).lower()
    if value.startswith("french"):
        return "fr"
    if value.startswith("english"):
        return "en"
    return "unk"


def infer_year(row) -> int | None:
    for col in ["time", "id", "minute_id"]:
        value = str(row.get(col, ""))
        m = re.search(r"(19\d{2})", value)
        if m:
            return int(m.group(1))
    return None


def split_refs(x) -> list[str]:
    if not isinstance(x, str) or not x.strip():
        return []
    return [r for r in x.split("|") if r]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÖØ-öø-ÿ]+", str(text).lower(), flags=re.UNICODE)


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.docs_tokens = [tokenize(d) for d in docs]
        self.k1 = k1
        self.b = b
        self.doc_len = [len(t) for t in self.docs_tokens]
        self.avgdl = sum(self.doc_len) / max(1, len(self.doc_len))
        self.tf = [Counter(t) for t in self.docs_tokens]
        df = Counter()
        for terms in self.docs_tokens:
            df.update(set(terms))
        n = len(self.docs_tokens)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query: str) -> list[float]:
        scores = [0.0] * len(self.docs_tokens)
        for term in set(tokenize(query)):
            if term not in self.idf:
                continue
            idf = self.idf[term]
            for i, tf in enumerate(self.tf):
                f = tf.get(term, 0)
                if not f:
                    continue
                dl = self.doc_len[i] or 1
                denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[i] += idf * f * (self.k1 + 1) / denom
        return scores


def read_dump(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        speeches = pd.read_csv(zf.open("csv/speeches.csv"))
        people = pd.read_csv(zf.open("csv/people.csv"))
    people_map = {r["id"]: clean_label(r.get("label", "")) for _, r in people.iterrows()}
    return speeches, people_map


def build_documents(speeches: pd.DataFrame, people_map: dict[str, str]) -> list[dict]:
    docs = []
    for _, row in speeches.iterrows():
        text = row.get("content")
        if not isinstance(text, str) or len(text.strip()) < 120:
            continue
        sid = short_id(row.get("id", ""))
        mid = short_id(row.get("minute_id", ""))
        speaker_id = row.get("speaker_id") if isinstance(row.get("speaker_id"), str) else ""
        speaker = people_map.get(speaker_id, clean_label(str(row.get("speaker", ""))))
        if not speaker:
            speaker = clean_label(str(row.get("label", ""))) or "Unknown speaker"
        docs.append({
            "doc_id": sid,
            "uri": row.get("id", ""),
            "source_url": f"{BASE_URL}/en/speeches/page/{sid}",
            "label": row.get("label", ""),
            "speaker_id": speaker_id,
            "speaker": speaker,
            "language": lang_code(row.get("language", "")),
            "language_label": row.get("language", ""),
            "year": infer_year(row),
            "minute_id": mid,
            "people_references": split_refs(row.get("people_references")),
            "place_references": split_refs(row.get("place_references")),
            "text": text.strip(),
        })
    return docs


def make_simple_questions(docs: list[dict], people_map: dict[str, str], n_per_split: int = 50) -> list[dict]:
    candidates = []
    seen = set()
    for d in docs:
        if d["language"] not in {"en", "fr"} or not d.get("year"):
            continue
        for rid in d.get("people_references", []):
            ent = people_map.get(rid)
            if not ent or ent == d["speaker"]:
                continue
            key = (d["speaker"], d["year"], ent, d["language"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"doc": d, "entity": ent})
    random.shuffle(candidates)
    pools = {("en", "en"): [], ("fr", "fr"): [], ("fr", "en"): [], ("en", "fr"): []}
    for c in candidates:
        for qlang, dlang in pools:
            if c["doc"]["language"] == dlang:
                pools[(qlang, dlang)].append(c)
    questions = []
    qid = 1
    for (qlang, dlang), pool in pools.items():
        for c in pool[:n_per_split]:
            d = c["doc"]
            ent = c["entity"]
            if qlang == "fr":
                question = f"Retrouvez l'intervention de {d['speaker']} en {d['year']} qui mentionne {ent}."
            else:
                question = f"Find the speech by {d['speaker']} in {d['year']} that mentions {ent}."
            questions.append({
                "qid": f"lon_{qid:04d}",
                "question": question,
                "query_language": qlang,
                "document_language": dlang,
                "gold_doc_id": d["doc_id"],
                "gold_source_url": d["source_url"],
                "speaker": d["speaker"],
                "year": d["year"],
                "entity": ent,
                "query_type": "singlehop_speaker_year_entity",
            })
            qid += 1
    random.shuffle(questions)
    return questions


def theme_for_doc(text: str) -> tuple[str, str] | None:
    low = text.lower()
    best = None
    best_hits = []
    for theme, cfg in THEMES.items():
        hits = [kw for kw in cfg["keywords"] if kw.lower() in low]
        if len(hits) > len(best_hits):
            best = theme
            best_hits = hits
    if best and best_hits:
        return best, " | ".join(best_hits[:8])
    return None


def excerpt_around_keywords(text: str, keywords: str, max_chars: int = 700) -> str:
    terms = [k.strip().lower() for k in keywords.split("|") if k.strip()]
    low = text.lower()
    pos = min([low.find(t) for t in terms if low.find(t) >= 0] or [0])
    start = max(0, pos - 250)
    end = min(len(text), start + max_chars)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def make_semantic_questions(docs: list[dict], n_per_split: int = 25) -> list[dict]:
    candidates = []
    for d in docs:
        if d["language"] not in {"en", "fr"} or not d.get("year") or len(d.get("text", "")) < 900:
            continue
        match = theme_for_doc(d["text"])
        if not match:
            continue
        theme, matched = match
        candidates.append({"doc": d, "theme": theme, "matched": matched})
    random.shuffle(candidates)

    pools = {("en", "en"): [], ("fr", "fr"): [], ("fr", "en"): [], ("en", "fr"): []}
    used_docs = set()
    for c in candidates:
        d = c["doc"]
        if d["doc_id"] in used_docs:
            continue
        for qlang, dlang in pools:
            if d["language"] == dlang:
                pools[(qlang, dlang)].append(c)
        used_docs.add(d["doc_id"])

    questions = []
    qid = 1
    for (qlang, dlang), pool in pools.items():
        selected = pool[:n_per_split]
        if len(selected) < n_per_split:
            print(f"WARNING: semantic split {qlang}->{dlang} has only {len(selected)} examples")
        for c in selected:
            d = c["doc"]
            template = THEMES[c["theme"]][qlang]
            if qlang == "fr":
                question = f"Retrouvez une intervention de {d['speaker']} en {d['year']} qui {template}."
            else:
                question = f"Find a speech by {d['speaker']} in {d['year']} that {template}."
            questions.append({
                "qid": f"lon_sem_{qid:04d}",
                "split": f"{qlang.upper()}→{dlang.upper()}",
                "query_lang": qlang,
                "doc_lang": dlang,
                "question": question,
                "theme": c["theme"],
                "gold_doc_id": d["doc_id"],
                "source_url": d["source_url"],
                "speaker": d["speaker"],
                "year": d["year"],
                "matched_keywords": c["matched"],
                "gold_excerpt": excerpt_around_keywords(d["text"], c["matched"]),
                "text_len": len(d["text"]),
            })
            qid += 1
    random.shuffle(questions)
    return questions


def write_jsonl(path: Path, rows: Iterable[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def rank_gold_with_bm25(docs: list[dict], questions: list[dict]) -> list[dict]:
    doc_ids = [d["doc_id"] for d in docs]
    texts = [" ".join([d.get("speaker", ""), str(d.get("year", "")), d.get("label", ""), d.get("text", "")]) for d in docs]
    bm25 = BM25(texts)
    rows = []
    for q in questions:
        scores = bm25.scores(q["question"])
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        gold = q["gold_doc_id"]
        rank = next((i + 1 for i, idx in enumerate(ranked) if doc_ids[idx] == gold), None)
        row = dict(q)
        row["bm25_rank"] = rank
        row["bm25_score"] = scores[doc_ids.index(gold)] if gold in doc_ids else 0.0
        row["R1"] = int(rank == 1)
        row["R3"] = int(rank is not None and rank <= 3)
        row["R5"] = int(rank is not None and rank <= 5)
        row["R10"] = int(rank is not None and rank <= 10)
        row["MRR"] = 0.0 if rank is None else 1.0 / rank
        rows.append(row)
    return rows


def write_summary(path: Path, rows: list[dict], split_key: str):
    groups = defaultdict(list)
    for r in rows:
        groups[r[split_key]].append(r)
    fieldnames = ["split", "n", "R1", "R3", "R5", "R10", "MRR"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for split, rs in sorted(groups.items()):
            w.writerow({
                "split": split,
                "n": len(rs),
                "R1": sum(r["R1"] for r in rs) / len(rs),
                "R3": sum(r["R3"] for r in rs) / len(rs),
                "R5": sum(r["R5"] for r in rs) / len(rs),
                "R10": sum(r["R10"] for r in rs) / len(rs),
                "MRR": sum(r["MRR"] for r in rs) / len(rs),
            })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path, help="Path to minutes-data-v1.1.0.zip")
    ap.add_argument("--out", required=True, type=Path, help="Output directory, e.g. data/processed")
    ap.add_argument("--semantic-per-split", type=int, default=25)
    ap.add_argument("--simple-per-split", type=int, default=50)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    speeches, people_map = read_dump(args.zip)
    docs = build_documents(speeches, people_map)
    write_jsonl(args.out / "lon_documents.jsonl", docs)

    simple = make_simple_questions(docs, people_map, args.simple_per_split)
    semantic = make_semantic_questions(docs, args.semantic_per_split)

    simple_ranked = rank_gold_with_bm25(docs, simple)
    semantic_ranked = rank_gold_with_bm25(docs, semantic)

    write_jsonl(args.out / "simple" / "lon_questions_200.jsonl", simple)
    write_jsonl(args.out / "semantic" / "lon_semantic_questions_100.jsonl", semantic)

    pd.DataFrame(semantic_ranked).assign(Status="", Issue_type="", Edited_question="", Reviewer_notes="").to_csv(args.out / "semantic" / "lon_semantic_questions_review.csv", index=False)
    pd.DataFrame(simple_ranked).to_csv(args.out / "simple" / "bm25_baseline_results.csv", index=False)

    write_summary(args.out / "simple" / "bm25_summary.csv", simple_ranked, "document_language")
    write_summary(args.out / "semantic" / "bm25_semantic_summary.csv", semantic_ranked, "split")

    summary = {
        "n_documents": len(docs),
        "n_simple_questions": len(simple),
        "n_semantic_questions": len(semantic),
        "languages": dict(Counter(d["language"] for d in docs)),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
