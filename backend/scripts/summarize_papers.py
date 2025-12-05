import argparse
import json
import os
from typing import Dict, List, Optional, Tuple

import httpx
from sqlmodel import Session, select

from backend.app.db import create_db_engine, init_db
from backend.app.models import Chunk, Paper, Summary, Tag


def get_llm_config() -> Dict[str, str]:
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    api_key = os.getenv("LLM_API_KEY")
    if not base_url or not model or not api_key:
        raise RuntimeError("Missing LLM configuration (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY).")
    return {"base_url": base_url, "model": model, "api_key": api_key}


def fetch_context(session: Session, paper_id: int, chunk_tokens: int) -> str:
    # Very simple: fetch first N characters worth of chunks in order.
    chunks = session.exec(
        select(Chunk)
        .where(Chunk.paper_id == paper_id)
        .order_by(Chunk.seq)
        .limit(10)
    ).all()
    ctx_parts: List[str] = []
    total = 0
    for c in chunks:
        if total >= chunk_tokens:
            break
        ctx_parts.append(c.content)
        total += len(c.content)
    return "\n\n".join(ctx_parts)


def build_prompt(title: str, abstract: str, context: str) -> str:
    return f"""
You are an expert paper analyst. Return ONLY valid JSON with BOTH English and Chinese fields:
{{
  "long_summary_en": [ "bullet 1", ... 4-8 bullets ],
  "long_summary_zh": [ "要点1", ... 4-8 bullets ],
  "one_liner_en": "English TL;DR one sentence",
  "one_liner_zh": "中文一句话总结",
  "snarky_comment_en": "witty but professional remark",
  "snarky_comment_zh": "简短犀利中文吐槽",
  "domains_en": ["domain1", "domain2"],
  "domains_zh": ["领域1", "领域2"],
  "tasks_en": ["task1", "task2"],
  "tasks_zh": ["任务1", "任务2"],
  "keywords_en": ["k1", "k2", ... up to 8],
  "keywords_zh": ["关键词1", "关键词2", ... up to 8]
}}
Use plain text, no Markdown fences, no extra keys.

Title: {title}
Abstract: {abstract}
Excerpts:
{context}
"""


def call_llm(prompt: str, cfg: Dict[str, str]) -> Dict[str, any]:
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        # Hint the API to return a JSON object if supported (OpenAI-style).
        "response_format": {"type": "json_object"},
    }
    resp = httpx.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(
            f"Invalid JSON from LLM (status {resp.status_code}): {resp.text[:500]}"
        )
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"Unexpected LLM response shape: {data}")
    # Normalize possible code fences and extract JSON substring.
    text = content.strip()
    if text.startswith("```"):
        # strip markdown fences like ```json ... ```
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    # Try to locate first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except Exception:
        raise RuntimeError(
            f"LLM content is not valid JSON. content_preview={text[:500]}"
        )


def upsert_summary_tags(session: Session, paper_id: int, model: str, result: Dict[str, any]):
    def normalize_text(value):
        if value is None:
            return None
        if isinstance(value, list):
            return "\n".join([str(v) for v in value])
        return str(value)

    # Prefer bilingual fields; fallback to legacy keys.
    def combine_bilingual(en_val, zh_val):
        parts = []
        if en_val:
            parts.append(normalize_text(en_val))
        if zh_val:
            parts.append(normalize_text(zh_val))
        return "\n".join([p for p in parts if p])

    long_summary = combine_bilingual(result.get("long_summary_en"), result.get("long_summary_zh")) or normalize_text(
        result.get("long_summary")
    )
    one_liner = combine_bilingual(result.get("one_liner_en"), result.get("one_liner_zh")) or normalize_text(
        result.get("one_liner")
    )
    snarky_comment = combine_bilingual(
        result.get("snarky_comment_en"), result.get("snarky_comment_zh")
    ) or normalize_text(result.get("snarky_comment"))

    summary = Summary(
        paper_id=paper_id,
        model=model,
        long_summary=long_summary,
        one_liner=one_liner,
        snarky_comment=snarky_comment,
    )
    session.add(summary)
    def add_tags(tag_type: str, values):
        for val in values or []:
            session.add(Tag(paper_id=paper_id, tag_type=tag_type, value=str(val)))

    add_tags("domains", result.get("domains_en") or result.get("domains"))
    add_tags("domains_zh", result.get("domains_zh"))
    add_tags("tasks", result.get("tasks_en") or result.get("tasks"))
    add_tags("tasks_zh", result.get("tasks_zh"))
    add_tags("keywords", result.get("keywords_en") or result.get("keywords"))
    add_tags("keywords_zh", result.get("keywords_zh"))


def process_papers(
    limit: Optional[int],
    chunk_chars: int,
    skip_existing: bool,
    dry_run: bool,
    progress_cb=None,
    stop_event=None,
):
    cfg = get_llm_config()
    engine = create_db_engine()
    init_db(engine)
    with Session(engine) as session:
        q = select(Paper).where(Paper.is_paper == True).order_by(Paper.id)
        if limit:
            q = q.limit(limit)
        papers = session.exec(q).all()
        total_papers = len(papers)
        if progress_cb:
            progress_cb(
                {
                    "stage": "starting",
                    "total_papers": total_papers,
                    "processed": 0,
                    "processed_papers": 0,
                    "errors": 0,
                }
            )
        processed = 0
        errors = 0
        for paper in papers:
            if stop_event and stop_event.is_set():
                if progress_cb:
                    progress_cb(
                        {
                            "stage": "stopped",
                            "processed": processed,
                            "processed_papers": processed,
                            "errors": errors,
                            "total_papers": total_papers,
                            "current_paper_id": paper.id,
                            "current_paper_title": paper.title,
                        }
                    )
                break
            if skip_existing:
                existing = session.exec(select(Summary).where(Summary.paper_id == paper.id)).first()
                if existing:
                    continue
            abstract = paper.abstract or ""
            context = fetch_context(session, paper.id, chunk_chars)
            prompt = build_prompt(paper.title or "(untitled)", abstract, context)
            try:
                result = call_llm(prompt, cfg)
            except Exception as exc:
                print(f"[ERROR] LLM call failed for paper {paper.id} ({paper.title}): {exc}")
                errors += 1
                if progress_cb:
                    progress_cb(
                        {
                            "stage": "error",
                            "paper_id": paper.id,
                            "paper_title": paper.title,
                            "error": str(exc),
                            "processed": processed,
                            "processed_papers": processed,
                            "errors": errors,
                            "total_papers": total_papers,
                            "current_paper_id": paper.id,
                            "current_paper_title": paper.title,
                        }
                    )
                continue
            if dry_run:
                print(json.dumps({"paper_id": paper.id, "title": paper.title, "result": result}, ensure_ascii=False))
                processed += 1
                if progress_cb:
                    progress_cb(
                        {
                            "stage": "done",
                            "paper_id": paper.id,
                            "paper_title": paper.title,
                            "processed": processed,
                            "processed_papers": processed,
                            "errors": errors,
                            "total_papers": total_papers,
                            "current_paper_id": paper.id,
                            "current_paper_title": paper.title,
                        }
                    )
                continue
            upsert_summary_tags(session, paper.id, cfg["model"], result)
            session.commit()
            processed += 1
            print(f"[OK] processed paper {paper.id} ({paper.title})")
            if progress_cb:
                progress_cb(
                    {
                        "stage": "done",
                        "paper_id": paper.id,
                        "paper_title": paper.title,
                        "processed": processed,
                        "processed_papers": processed,
                        "errors": errors,
                            "total_papers": total_papers,
                            "current_paper_id": paper.id,
                            "current_paper_title": paper.title,
                        }
                    )
    print(f"Done. processed={processed}")
    if progress_cb:
        progress_cb(
            {
                "stage": "finished",
                "processed": processed,
                "processed_papers": processed,
                "errors": errors,
                "total_papers": total_papers,
            }
        )


def main():
    parser = argparse.ArgumentParser(description="Generate summaries/tags for papers.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of papers.")
    parser.add_argument("--chunk-chars", type=int, default=4000, help="Approx chars of context to send.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip papers with existing summary.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write DB, just print results.")
    args = parser.parse_args()
    process_papers(
        limit=args.limit,
        chunk_chars=args.chunk_chars,
        skip_existing=args.skip_existing,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
