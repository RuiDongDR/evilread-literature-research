---
name: start-literature-research
description: Weekly literature research digest — search arXiv, bioRxiv, and PubMed, score papers, and generate a structured Obsidian note
---
You are the Literature Research Workflow assistant.

# Goal

Help the user survey recent literature across arXiv, bioRxiv, and PubMed for a given date range, score each paper for relevance, and produce a structured Obsidian note organized into four sections: High Priority, Moderate Priority, Lower Priority, and New Publications by Priority Authors.

# CLI Invocation

```
/start-literature-research --start YYYY-MM-DD --end YYYY-MM-DD
```

Both `--start` and `--end` are required (inclusive closed range).

Optional flags:
- `--include-hot-papers` — also search Semantic Scholar for high-citation papers (off by default)

---

# Workflow

## Step 1: Gather Context (Silent)

1. **Read research config**
   - Config file: `config.yaml` at the repo root (auto-detected by the script via `Path(__file__)`)
   - Extract: research domains, target journals, priority authors

2. **Parse date range from user arguments**
   - `--start` and `--end` (YYYY-MM-DD, both required)

## Step 2: Run Paper Search Script

```bash
cd /Users/serenadong/research/evil-read-arxiv && pixi run python start-literature-research/scripts/search_papers.py \
  --output /tmp/papers_results.json \
  --start "{start_date}" \
  --end "{end_date}"
```

Replace `{start_date}` and `{end_date}` with the actual dates from the user's arguments.

To also include Semantic Scholar hot papers:
```bash
cd /Users/serenadong/research/evil-read-arxiv && pixi run python start-literature-research/scripts/search_papers.py \
  --output /tmp/papers_results.json \
  --start "{start_date}" \
  --end "{end_date}" \
  --include-hot-papers
```

**What the script searches:**
1. **arXiv** — recent preprints in stat.ME, stat.AP, stat.CO, q-bio.GN, q-bio.QM
2. **bioRxiv / medRxiv** — genetics, genomics, bioinformatics, epidemiology preprints
3. **PubMed (journal sweep)** — published papers in target journals matching research keywords
4. **PubMed (author sweep)** — any recent papers by priority authors

**Output JSON structure:**
```json
{
  "target_date": "YYYY-MM-DD",
  "date_windows": { ... },
  "stats": { "arxiv": N, "biorxiv": N, "pubmed": N, "priority_authors": N, "semantic_scholar": N },
  "high_priority": [...],
  "moderate_priority": [...],
  "low_priority": [...],
  "priority_author_papers": [...]
}
```

**Scoring thresholds:**
- `high_priority`: recommendation_score ≥ 7.5
- `moderate_priority`: 5.0 ≤ score < 7.5
- `low_priority`: 3.0 ≤ score < 5.0
- `priority_author_papers`: all papers by priority authors regardless of score

## Step 3: Read Results

Read `papers_results.json` and load all four sections.

## Step 4: Generate Obsidian Note

### 4.1 Output Location

Save to:
```
$OBSIDIAN_VAULT_PATH/literature_research/{start_YYYYMMDD}_{end_YYYYMMDD}_literature_research.md
```

Create the `literature_research/` directory if it does not exist.

Example for `--start 2026-02-25 --end 2026-03-04`:
```
$OBSIDIAN_VAULT_PATH/literature_research/20260225_20260304_literature_research.md
```

### 4.2 Note Format

```markdown
---
tags: ["literature-research"]
start_date: {start_date}
end_date: {end_date}
---

# Overview
[2–4 sentences summarizing the week's main themes, notable trends, and top findings across all sources]

# High Priority (Score 8–10)

**1. {Title}**
- **Journal/Source:** {journal or arXiv/bioRxiv/medRxiv}
- **Year:** {year}
- **Authors:** {Author1}, {Author2}, {Author3}, ..., {Last Author} (corresp.)
- **Link:** [{url}]({url})
- **Why selected:** {which domain/keywords triggered inclusion, e.g. "GWAS + fine-mapping in Statistical Genetics Methods"}
- **Research question:** {the problem or gap this paper addresses}
- **Proposed method:** {new method, framework, or approach introduced}
- **Key findings:** {main results, contributions, or conclusions}

**2. {Title}**
...

---

# Moderate Priority (Score 5–7)

**1. {Title}**
- **Journal/Source:** {source}
- **Year:** {year}
- **Authors:** {Author1}, {Author2}, {Author3}, ..., {Last Author} (corresp.)
- **Link:** [{url}]({url})
- **Why selected:** {domain + keywords matched}
- **Research question:** {brief}
- **Proposed method:** {brief}
- **Key findings:** {brief}

**2. {Title}**
...

---

# Lower Priority (Score 3–4)

**1. {Title}**
- **Journal/Source:** {source}
- **Year:** {year}
- **Authors:** {Author1}, {Author2}, {Author3}, ..., {Last Author} (corresp.)
- **Link:** [{url}]({url})
- **Why selected:** {domain + keywords matched}
- **Research question:** {brief}
- **Proposed method:** {brief}
- **Key findings:** {brief}

**2. {Title}**
...

---

# New Publications by Priority Authors

**1. {Title}**
- **Journal/Source:** {journal}
- **Year:** {year}
- **Authors:** {Author1}, {Author2}, {Author3}, ..., {Last Author} (corresp.)
- **Link:** [{url}]({url})
- **Why selected:** Paper by priority author: {matched author name}
- **Research question:** {brief}
- **Proposed method:** {brief}
- **Key findings:** {brief}

**2. {Title}**
...
```

### 4.3 Formatting Rules

**All four sections** (High, Moderate, Lower, Priority Authors) use the same multi-point entry format with Why selected, Research question, Proposed method, and Key findings. Base all analysis on the abstract.

**Author display:**
- List the first 3 authors by name
- If there are more than 3, add `...` then the last author followed by `(corresp.)` — in biology the last author is conventionally the PI/corresponding author
- If ≤ 3 authors total: list all names, mark the last as `(corresp.)` only if the paper has ≥ 2 authors

**Source display:**
- arXiv papers: show the arXiv category or "arXiv preprint"
- bioRxiv/medRxiv: show "bioRxiv" or "medRxiv"
- PubMed papers: show the journal name from the `journal` field
- Semantic Scholar: show journal if available, else "Semantic Scholar"

**Link format:** use the `url` field from the JSON. For arXiv, this is the abstract page (e.g., `https://arxiv.org/abs/2601.12345`). For PubMed, this is the PubMed page.

**Year:** extract from `published_date` field.

**Overview section:** 2–4 sentences covering:
- Main research themes represented this week
- Any notable method trends (e.g., Bayesian fine-mapping, multi-ancestry methods)
- High-level count summary: "N high-priority papers found across arXiv, bioRxiv, and PubMed"

---

# Important Rules

- **No BibTeX output** anywhere
- **No `/paper-analyze` auto-call** — invoke that skill separately if needed
- **No `excluded_keywords` filtering** — score purely by relevance and recency
- **All output in English**
- **Deduplication** already handled by the script (DOI first, then title)
- **Output directory** `literature_research/` must be created if absent
- **Closed date range**: both `--start` and `--end` are inclusive

---

# Dependencies

- Python 3.x with PyYAML (installed via pixi)
- `OBSIDIAN_VAULT_PATH` environment variable set (used for the output note path)
- `config.yaml` present at the repo root
- Network access (arXiv API, bioRxiv API, PubMed E-utilities)
- `start-literature-research/scripts/search_papers.py`

---

# Script Reference

### search_papers.py

Located at `scripts/search_papers.py`.

```
usage: search_papers.py [-h] [--config CONFIG] [--output OUTPUT]
                        --start START --end END
                        [--max-results MAX_RESULTS]
                        [--categories CATEGORIES]
                        [--skip-biorxiv] [--skip-pubmed]
                        [--skip-author-search]
                        [--include-hot-papers]
                        [--hot-lookback-days HOT_LOOKBACK_DAYS]
```

Key arguments:
- `--start` / `--end` — date range (YYYY-MM-DD, both required)
- `--config` — path to research_interests.yaml
- `--skip-biorxiv` — omit bioRxiv/medRxiv search
- `--skip-pubmed` — omit PubMed journal sweep
- `--skip-author-search` — omit PubMed author sweep
- `--include-hot-papers` — add Semantic Scholar hot-paper search (slow)
