# evil-read-arxiv

Automated research paper workflow — multi-source literature search, scoring, and Obsidian note generation, powered by [Claude Code](https://claude.ai/claude-code) skills.

## What It Does

Runs a literature digest across arXiv, bioRxiv/medRxiv, and PubMed for a given date range, scores each paper for relevance to your research interests, and saves a structured Obsidian note organized into:

- **Must-Read** (score ≥ 10) — exceptional match; read these first
- **High Priority** (7.5–9.9) — closely matching your domains and keywords
- **Moderate Priority** (5–7.5) — relevant but lower match
- **Lower Priority** (3–5) — tangentially related
- **New Publications by Priority Authors** — always surfaced regardless of score

## Skills Included

| Skill | Command | Description |
|-------|---------|-------------|
| `start-literature-research` | `/start-literature-research --start YYYYMMDD --end YYYYMMDD` | Literature digest for a date range |
| `paper-analyze` | `/paper-analyze <arXiv ID or title>` | Deep analysis of a single paper |
| `extract-paper-images` | `/extract-paper-images <arXiv ID>` | Extract figures from a paper |
| `paper-search` | `/paper-search "<query>"` | Search existing paper notes in your vault |

---

## Setup (macOS)

### 1. Clone the repo and install dependencies

[pixi](https://pixi.sh) manages the Python environment:

```bash
git clone https://github.com/your-username/evil-read-arxiv.git
cd evil-read-arxiv

# Install pixi if you don't have it
curl -fsSL https://pixi.sh/install.sh | bash

pixi install
```

### 2. Install the skills into Claude Code

```bash
cp -r start-literature-research ~/.claude/skills/
cp -r paper-analyze ~/.claude/skills/
cp -r extract-paper-images ~/.claude/skills/
cp -r paper-search ~/.claude/skills/
```

Restart Claude Code after copying.

### 3. Set your Obsidian vault path

Add `OBSIDIAN_VAULT_PATH` to your shell profile:

```bash
echo 'export OBSIDIAN_VAULT_PATH="/path/to/your/obsidian/vault"' >> ~/.zshrc
source ~/.zshrc
```

### 4. Configure your research interests

Edit `config.yaml` in the repo root to set your vault path, research domains, target journals, and priority authors. The file is read directly by the scripts — no copying needed.

```yaml
vault_path: "/path/to/your/obsidian/vault"

research_domains:
  "Statistical Genetics Methods":
    keywords:
      high:
        - "fine-mapping"
        - "causal variant"
      medium:
        - "GWAS"
      low:
        - "eQTL"
        - "polygenic risk score"
        - "Mendelian randomization"
    arxiv_categories:
      - "q-bio.GN"
    priority: 5

target_journals:
  - "Nature Genetics"
  - "American Journal of Human Genetics"

priority_authors:
  - "Matthew Stephens"
  - "Peter Visscher"
```

**Private author lists:** If you want to keep a longer or personal author list out of git, create `config.local.yaml` at the repo root (same format as `config.yaml`). It is gitignored and takes precedence automatically when running scripts directly.

### 5. Open Claude Code in your vault

```bash
cd "$OBSIDIAN_VAULT_PATH"
claude
```

---

## Usage

### Literature search

```
/start-literature-research --start 20260225 --end 20260304
```

Dates are `YYYYMMDD`, both inclusive. The note is saved to:

```
$OBSIDIAN_VAULT_PATH/literature_research/20260225_20260304_literature_research.md
```

To also include Semantic Scholar high-citation papers (slower):

```
/start-literature-research --start 20260225 --end 20260304 --include-hot-papers
```

### Analyze a specific paper

```
/paper-analyze 2602.12345
/paper-analyze "Attention Is All You Need"
```

### Extract paper figures

```
/extract-paper-images 2602.12345
```

### Search existing notes

```
/paper-search "fine-mapping eQTL"
```

---

## Config Reference

### Research domains

Each domain has:

| Field | Description |
|-------|-------------|
| `keywords.high` | Core terms — a single title match is enough to surface the paper |
| `keywords.medium` | Important but broader terms |
| `keywords.low` | Supporting vocabulary — needs multiple matches to score highly |
| `arxiv_categories` | arXiv categories to search (see table below) |
| `priority` | 1–5, higher = stronger score boost |

A flat keyword list (no tier keys) is also accepted and treated as all `low`.

### Common arXiv categories

| Code | Name |
|------|------|
| `stat.ME` | Statistics — Methodology |
| `stat.AP` | Statistics — Applications |
| `stat.CO` | Statistics — Computation |
| `q-bio.GN` | Quantitative Biology — Genomics |
| `q-bio.QM` | Quantitative Biology — Quantitative Methods |
| `q-bio.PE` | Quantitative Biology — Populations and Evolution |

### Scoring

```
Score = relevance (40%) + recency (20%) + popularity (30%) + quality (10%)
```

| Section | Score range |
|---------|-------------|
| Must-Read | ≥ 10 |
| High Priority | 7.5 – 9.9 |
| Moderate Priority | 5.0 – 7.5 |
| Lower Priority | 3.0 – 5.0 |
| Priority Authors | any (always included) |

---

## Repository Structure

```
evil-read-arxiv/
├── README.md
├── pixi.toml                          # Python dependency spec
├── config.yaml                        # Public config template — edit this
├── config.local.yaml                  # (gitignored) Personal override
├── start-literature-research/
│   ├── skill.md                       # Claude Code skill definition
│   └── scripts/
│       ├── search_papers.py           # arXiv / bioRxiv / PubMed search + scoring
│       └── generate_note.py           # Obsidian note generation
├── paper-analyze/
│   ├── skill.md
│   └── scripts/
│       ├── generate_note.py
│       └── update_graph.py
├── extract-paper-images/
│   ├── skill.md
│   └── scripts/
│       └── extract_images.py
└── paper-search/
    └── skill.md
```

---

## How It Works

```
/start-literature-research --start YYYYMMDD --end YYYYMMDD
         |
         v
1. Load config (config.local.yaml if present, else config.yaml)
         |
         v
2. Search arXiv           — by category + date window
3. Search bioRxiv/medRxiv — by subject + date window
4. Search PubMed          — target journals × keywords
5. Search PubMed          — papers by priority authors
[6. Optional: Semantic Scholar — high-citation papers]
         |
         v
7. Deduplicate (DOI first, then normalized title)
8. Score each paper
         |
         v
9. Bucket into Must-Read / High / Moderate / Low / Priority Authors
         |
         v
10. Claude writes the Obsidian note + overview paragraph
```

---

## Troubleshooting

**Config not found**
```bash
ls config.yaml   # must exist at the repo root
```

**No papers returned from arXiv**
- Broaden the date range; arXiv submission windows vary by day of week
- Check that your `arxiv_categories` are valid codes (see table above)

**PubMed returns nothing**
- PubMed E-utilities allows ~3 req/s without an API key; the script respects this automatically
- Try `--skip-pubmed` to isolate the issue:
  ```
  /start-literature-research --start 20260225 --end 20260304 --skip-pubmed
  ```

**Paper image extraction fails**
- Confirm PyMuPDF: `pixi run python -c "import fitz; print(fitz.__version__)"`
- Check arXiv ID format: `2602.12345` (no `arxiv:` prefix)

---

## Advanced: Run Scripts Directly

```bash
# arXiv + bioRxiv only, skip PubMed
pixi run python start-literature-research/scripts/search_papers.py \
  --output /tmp/results.json \
  --start 20260225 --end 20260304 \
  --skip-pubmed --skip-author-search

# Include Semantic Scholar hot papers
pixi run python start-literature-research/scripts/search_papers.py \
  --output /tmp/results.json \
  --start 20260225 --end 20260304 \
  --include-hot-papers --hot-lookback-days 60

# Use a custom config
pixi run python start-literature-research/scripts/search_papers.py \
  --config /path/to/custom_config.yaml \
  --output /tmp/results.json \
  --start 20260225 --end 20260304

# Regenerate note from existing results JSON
pixi run python start-literature-research/scripts/generate_note.py \
  --input /tmp/results.json \
  --output "$OBSIDIAN_VAULT_PATH/literature_research/20260225_20260304_literature_research.md" \
  --start 20260225 --end 20260304
```

---

## Acknowledgments

- [arXiv](https://arxiv.org/) — open-access preprint platform
- [bioRxiv](https://www.biorxiv.org/) / [medRxiv](https://www.medrxiv.org/) — life sciences preprint servers
- [PubMed](https://pubmed.ncbi.nlm.nih.gov/) — NCBI biomedical literature database
- [Semantic Scholar](https://www.semanticscholar.org/) — AI-powered academic research platform
- [Claude Code](https://claude.ai/claude-code) — AI-assisted development environment
- [Obsidian](https://obsidian.md/) — knowledge management tool

## License

MIT License
