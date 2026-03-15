import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


EN_STOPWORDS = {
    "about",
    "after",
    "also",
    "among",
    "approach",
    "based",
    "between",
    "does",
    "from",
    "have",
    "into",
    "main",
    "method",
    "model",
    "paper",
    "results",
    "show",
    "study",
    "that",
    "their",
    "these",
    "this",
    "using",
    "with",
}


def load_papers(db_path: Path) -> List[Tuple[int, str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT p.id, COALESCE(p.title, ''), COALESCE(s.one_liner, '')
            FROM paper p
            JOIN chunk c ON c.paper_id = p.id
            LEFT JOIN summary s ON s.paper_id = p.id
            WHERE p.is_paper = 1
            GROUP BY p.id
            ORDER BY p.id
            """
        ).fetchall()
    finally:
        conn.close()
    return [(int(row[0]), row[1], row[2]) for row in rows]


def deterministic_sample(rows: Sequence[Tuple[int, str, str]], target_n: int) -> List[Tuple[int, str, str]]:
    if target_n >= len(rows):
        return list(rows)
    sampled: List[Tuple[int, str, str]] = []
    used_ids = set()
    stride = len(rows) / float(target_n)
    cursor = 0.0
    while len(sampled) < target_n:
        idx = min(int(cursor), len(rows) - 1)
        while idx < len(rows) and rows[idx][0] in used_ids:
            idx += 1
        if idx >= len(rows):
            break
        sampled.append(rows[idx])
        used_ids.add(rows[idx][0])
        cursor += stride
    if len(sampled) < target_n:
        for row in rows:
            if row[0] in used_ids:
                continue
            sampled.append(row)
            used_ids.add(row[0])
            if len(sampled) >= target_n:
                break
    return sampled


def extract_expected_terms(title: str, one_liner: str) -> List[str]:
    text = f"{title} {one_liner}".lower()
    en_tokens = re.findall(r"[a-z0-9]{4,}", text)
    terms: List[str] = []
    for token in en_tokens:
        if token in EN_STOPWORDS:
            continue
        if token not in terms:
            terms.append(token)
        if len(terms) >= 2:
            return terms
    zh_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for token in zh_tokens:
        if token not in terms:
            terms.append(token)
        if len(terms) >= 2:
            break
    return terms[:2]


def build_cases(rows: Sequence[Tuple[int, str, str]]) -> List[Dict[str, Any]]:
    paper_templates = [
        ("core", "What is the core method and main contribution of this paper?"),
        ("evidence", "What problem does this paper solve and what evidence supports the claim?"),
        ("limits", "What limitations or trade-offs are discussed in this paper?"),
    ]
    cases: List[Dict[str, Any]] = []
    for idx, (paper_id, title, one_liner) in enumerate(rows):
        template_key, query = paper_templates[idx % len(paper_templates)]
        expected_terms = extract_expected_terms(title=title, one_liner=one_liner)
        case = {
            "id": f"paper-{paper_id}-{template_key}",
            "query": query,
            "scope": "paper",
            "paper_id": paper_id,
            "candidate_k": 20,
            "final_k": 6,
            "rerank": True,
            "require_citations": True,
            "expected_terms": expected_terms[:1],
        }
        cases.append(case)

    library_cases = [
        {
            "id": "library-cross-1",
            "query": "Compare two representative approaches and their tradeoffs.",
            "scope": "library",
            "expected_terms": ["tradeoff", "performance"],
        },
        {
            "id": "library-cross-2",
            "query": "What recurring limitations appear across these papers?",
            "scope": "library",
            "expected_terms": ["limitation"],
        },
        {
            "id": "library-cross-3",
            "query": "Summarize the common evaluation settings and benchmark patterns.",
            "scope": "library",
            "expected_terms": ["benchmark"],
        },
        {
            "id": "library-cross-4",
            "query": "Which methods emphasize efficiency over peak accuracy?",
            "scope": "library",
            "expected_terms": ["efficiency", "accuracy"],
        },
        {
            "id": "library-cross-5",
            "query": "Give a concise taxonomy of solution paradigms in this library.",
            "scope": "library",
            "expected_terms": ["taxonomy"],
        },
        {
            "id": "library-cross-6",
            "query": "请总结这个方向的关键挑战，并给出证据。",
            "scope": "library",
            "expected_terms": ["挑战", "证据"],
        },
        {
            "id": "library-cross-7",
            "query": "请比较两类主流方法的优缺点，并给出引用。",
            "scope": "library",
            "expected_terms": ["优缺点"],
        },
        {
            "id": "library-cross-8",
            "query": "请说明当前方法在真实部署时最常见的瓶颈。",
            "scope": "library",
            "expected_terms": ["瓶颈"],
        },
        {
            "id": "library-no-answer-1",
            "query": "What exact production revenue number is reported across the papers?",
            "scope": "library",
            "expected_terms": [],
        },
        {
            "id": "library-no-answer-2",
            "query": "Which paper discloses customer names from a commercial contract?",
            "scope": "library",
            "expected_terms": [],
        },
        {
            "id": "library-no-answer-3",
            "query": "Give the exact stock ticker and quarterly EPS for every method.",
            "scope": "library",
            "expected_terms": [],
        },
        {
            "id": "library-long-1",
            "query": "Provide a long-form synthesis of methods, limitations, and future directions with structured evidence.",
            "scope": "library",
            "candidate_k": 30,
            "final_k": 8,
            "rerank": True,
            "require_citations": True,
            "expected_terms": ["future"],
        },
        {
            "id": "library-long-2",
            "query": "Create a multi-paragraph comparison across datasets, metrics, and compute cost trends.",
            "scope": "library",
            "candidate_k": 30,
            "final_k": 8,
            "rerank": True,
            "require_citations": True,
            "expected_terms": ["dataset", "metrics"],
        },
    ]
    cases.extend(library_cases)
    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a corpus-scale local RAG evaluation set.")
    parser.add_argument("--db", type=Path, default=Path("paper_agent.db"))
    parser.add_argument("--paper-cases", type=int, default=96)
    parser.add_argument("--output", type=Path, default=Path("backend/eval/rag_eval_cases_baseline_1500.json"))
    return parser.parse_args()


def main():
    args = parse_args()
    rows = load_papers(args.db)
    sampled = deterministic_sample(rows, max(1, args.paper_cases))
    cases = build_cases(sampled)
    payload = {
        "meta": {
            "paper_total_with_chunks": len(rows),
            "paper_cases": len(sampled),
            "total_cases": len(cases),
        },
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "paper_total_with_chunks": len(rows),
                "paper_cases": len(sampled),
                "total_cases": len(cases),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
