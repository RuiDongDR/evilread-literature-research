#!/usr/bin/env python3
"""
Generate an Obsidian literature-research note from papers_results.json.

Usage:
    python generate_note.py \
        --input /tmp/papers_results.json \
        --output /path/to/vault/literature_research/YYYYMMDD_YYYYMMDD_literature_research.md
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_authors(authors: list) -> str:
    if not authors:
        return "N/A"
    if len(authors) > 3:
        return ", ".join(authors[:3]) + ", ..., " + authors[-1] + " (corresp.)"
    elif len(authors) >= 2:
        return ", ".join(authors[:-1]) + ", " + authors[-1] + " (corresp.)"
    return authors[0]


def get_date(p: dict) -> str:
    date_str = p.get("published_date", "") or ""
    if not date_str:
        return "N/A"
    # Normalize to YYYY-MM-DD (handle YYYY-MM-DD or YYYYMMDD)
    s = str(date_str).strip()
    if len(s) == 8 and s.isdigit():
        s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    source = p.get("source", "")
    if source in ("arxiv", "biorxiv", "medrxiv"):
        return f"Posted {s}"
    return f"Published {s}"


def get_source(p: dict) -> str:
    source = p.get("source", "")
    journal = p.get("journal", "")
    if source == "arxiv":
        cats = p.get("categories", [])
        cat = cats[0] if cats else ""
        return f"arXiv preprint ({cat})" if cat else "arXiv preprint"
    elif source == "biorxiv":
        return "bioRxiv"
    elif source == "medrxiv":
        return "medRxiv"
    elif source == "pubmed" and journal:
        return " ".join(w.capitalize() for w in journal.split())
    return source


def get_why(p: dict) -> str:
    domain = p.get("matched_domain", "")
    keywords = p.get("matched_keywords", []) or []
    authors_matched = p.get("matched_authors", []) or []
    parts = []
    if domain:
        parts.append(domain)
    # Exclude bare category strings like "stat.ME" from keyword display
    kw_display = [k for k in keywords if "." not in k or " " in k]
    if kw_display:
        parts.append(", ".join(kw_display[:5]))
    if authors_matched:
        parts.append("priority authors: " + ", ".join(authors_matched))
    return "; ".join(parts) if parts else "Matched research domain keywords"


def split_sentences(text: str) -> list:
    """Split text into sentences at . ! ? boundaries."""
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if s.strip()]


def first_n_complete_sentences(text: str, n: int = 2, max_chars: int = 400) -> str:
    """Return the first n complete sentences, never truncating mid-sentence.
    Falls back to 1 sentence if the first sentence alone exceeds max_chars.
    """
    sentences = split_sentences(text)
    if not sentences:
        return text[:max_chars] if text else "N/A"
    result = []
    total = 0
    for s in sentences[:n]:
        if total + len(s) > max_chars and result:
            break
        result.append(s)
        total += len(s)
    return " ".join(result) if result else sentences[0][:max_chars]


def parse_abstract(abstract: str) -> tuple:
    """Return (research_question, proposed_method, key_findings) from abstract.

    Strategy:
    - Research question: first sentence(s) that frame a problem/gap.
    - Proposed method: sentence(s) that introduce a new approach.
    - Key findings: last sentence(s) that describe results/conclusions.

    All are complete sentences, never truncated mid-word.
    """
    if not abstract:
        return "Not available.", "Not available.", "Not available."

    sentences = split_sentences(abstract)
    if not sentences:
        return abstract[:200], "N/A", "N/A"

    # Keyword patterns
    method_pats = re.compile(
        r"\b(we propose|we present|we introduce|we develop|we derive|we leverage|"
        r"we design|we build|our method|our approach|our framework|our model|"
        r"in this (paper|work|study)|we show|we demonstrate)\b",
        re.IGNORECASE,
    )
    finding_pats = re.compile(
        r"\b(we find|results show|we demonstrate|outperform|improve|achieve|"
        r"our (results|experiments|analysis|evaluation)|significantly|"
        r"in (summary|conclusion|conclusion)|we conclude|application to|"
        r"applied to|on real data|in simulations?)\b",
        re.IGNORECASE,
    )
    problem_pats = re.compile(
        r"\b(challenge|however|yet|despite|lack|limited|difficult|gap|remain|"
        r"problem|aim to|goal is|objective|motivated by|existing methods|"
        r"traditional|previous)\b",
        re.IGNORECASE,
    )

    rq_sents, method_sents, finding_sents = [], [], []
    for s in sentences:
        if method_pats.search(s):
            method_sents.append(s)
        elif finding_pats.search(s):
            finding_sents.append(s)
        elif problem_pats.search(s):
            rq_sents.append(s)

    # Fallbacks
    if not rq_sents:
        rq_sents = sentences[:1]
    if not method_sents:
        mid = len(sentences) // 2
        method_sents = sentences[mid : mid + 1]
    if not finding_sents:
        finding_sents = sentences[-1:]

    rq = first_n_complete_sentences(" ".join(rq_sents), n=2, max_chars=350)
    method = first_n_complete_sentences(" ".join(method_sents), n=2, max_chars=350)
    findings = first_n_complete_sentences(" ".join(finding_sents), n=2, max_chars=350)

    return rq, method, findings


def make_entry(p: dict, idx: int) -> str:
    authors = p.get("authors", [])
    scores = p.get("scores", {})
    rec_score = scores.get("recommendation", "N/A")
    score_str = f"{rec_score:.1f}" if isinstance(rec_score, float) else str(rec_score)
    abstract = (p.get("abstract") or "").strip()
    rq, method, findings = parse_abstract(abstract)
    url = p.get("url", "N/A")

    lines = [
        f"**{idx}. {p['title']}**",
        f"- **Journal/Source:** {get_source(p)}",
        f"- **Date:** {get_date(p)}",
        f"- **Authors:** {format_authors(authors)}",
        f"- **Link:** [{url}]({url})",
        f"- **Why selected:** {get_why(p)}",
        f"- **Research question:** {rq}",
        f"- **Proposed method:** {method}",
        f"- **Key findings:** {findings}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Obsidian literature note")
    parser.add_argument("--input", required=True, help="Path to papers_results.json")
    parser.add_argument("--output", required=True, help="Output .md path")
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    MUST_READ_CUTOFF = 10.0

    stats = data.get("stats", {})
    _high_all = data.get("high_priority", [])
    must_read = [p for p in _high_all if (p.get("scores", {}).get("recommendation", 0) or 0) >= MUST_READ_CUTOFF]
    high = [p for p in _high_all if (p.get("scores", {}).get("recommendation", 0) or 0) < MUST_READ_CUTOFF]
    moderate = data.get("moderate_priority", [])
    low = data.get("low_priority", [])

    # Read dates from JSON
    recent = data.get("date_windows", {}).get("recent", {})
    s = recent.get("start", "")
    e = recent.get("end", "")
    start_disp = f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 else s
    end_disp = f"{e[:4]}-{e[4:6]}-{e[6:]}" if len(e) == 8 else e

    lines = []
    lines.append("---")
    lines.append('tags: ["literature-research"]')
    lines.append(f"start_date: {s}")
    lines.append(f"end_date: {e}")
    lines.append("---")
    lines.append("")
    lines.append("# Overview")
    lines.append("")
    lines.append(
        f"Literature survey for {start_disp} to {end_disp} across arXiv "
        f"({stats.get('arxiv', 0)} papers), bioRxiv/medRxiv ({stats.get('biorxiv', 0)} papers), "
        f"and PubMed ({stats.get('pubmed', 0)} papers). "
        f"Identified {len(must_read)} must-read, {len(high)} high-priority, "
        f"{len(moderate)} moderate-priority, and {len(low)} lower-priority papers across all sources."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Must-read
    lines.append("# Must-Read (Score ≥ 10)")
    lines.append("")
    if must_read:
        for i, p in enumerate(must_read, 1):
            lines.append(make_entry(p, i))
            lines.append("")
    else:
        lines.append("*No papers reached the must-read threshold this period.*")
        lines.append("")

    lines.append("---")
    lines.append("")

    # High priority
    lines.append("# High Priority (Score 7.5–9.9)")
    lines.append("")
    for i, p in enumerate(high, 1):
        lines.append(make_entry(p, i))
        lines.append("")

    lines.append("---")
    lines.append("")

    # Moderate priority
    lines.append("# Moderate Priority (Score 5–7.5)")
    lines.append("")
    for i, p in enumerate(moderate, 1):
        lines.append(make_entry(p, i))
        lines.append("")

    lines.append("---")
    lines.append("")

    # Lower priority
    lines.append("# Lower Priority (Score 3–5)")
    lines.append("")
    for i, p in enumerate(low, 1):
        lines.append(make_entry(p, i))
        lines.append("")


    content = "\n".join(lines)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    print(f"Note written to {out_path} ({len(content):,} chars, {content.count(chr(10))} lines)")
    print(f"  Must-read: {len(must_read)}, High: {len(high)}, Moderate: {len(moderate)}, Low: {len(low)}")


if __name__ == "__main__":
    main()
