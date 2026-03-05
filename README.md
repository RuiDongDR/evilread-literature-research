# evilread-literature-research

Automated research paper workflow — multi-source literature search, scoring, and Obsidian note generation.

This repo is customized for my research interests and needs, inspired by the [original repo: evil-read-arxiv](https://github.com/juliye2025/evil-read-arxiv).

## What It Does

Runs a literature digest across arXiv, bioRxiv/medRxiv, and PubMed for a given date range, scores each paper for relevance to your research interests, and saves a structured Obsidian note organized into:

- **Must-Read** (score ≥ 10) — exceptional match; read these first
- **High Priority** (7.5–9.9) — closely matching your domains and keywords
- **Moderate Priority** (5–7.5) — relevant but lower match
- **Lower Priority** (3–5) — tangentially related
- **New Publications by Priority Authors** — always surfaced regardless of score

## Setup (macOS)

### 1. Clone the repo and install dependencies

[pixi](https://pixi.sh) manages the Python environment:

```bash
git clone https://github.com/RuiDongDR/evilread-literature-research.git
cd evilread-literature-research

# Install pixi if you don't have it
curl -fsSL https://pixi.sh/install.sh | bash

pixi install
```

### 2. Install the skills into Claude Code (if run as a prompt in Claude)

First, find your Claude Code skills directory:

```bash
# Claude Code stores skills here by default:
ls ~/.claude/skills/

# If that path doesn't exist, find the actual Claude config directory:
claude --version          # confirm Claude Code is installed
ls ~/.claude/             # inspect the config root
```

Once confirmed, copy the skill:

```bash
cp -r start-literature-research ~/.claude/skills/
```

Restart Claude Code after copying.

### 3. Set your Obsidian vault path

First, find your Obsidian vault location:

```bash
# On macOS, vaults are typically under ~/Documents or ~/Library:
ls ~/ | grep -i obsidian
ls ~/Documents/ | grep -i obsidian

# Or check Obsidian's config for all known vaults:
cat ~/Library/Application\ Support/obsidian/obsidian.json | grep -A2 '"path"'
```

Then add `OBSIDIAN_VAULT_PATH` to your shell profile, replacing `<PATH_TO_YOUR_OBSIDIAN_VAULT>` with the path you found above:

```bash
OBSIDIAN_VAULT_PATH="<PATH_TO_YOUR_OBSIDIAN_VAULT>"
echo "export OBSIDIAN_VAULT_PATH=\"$OBSIDIAN_VAULT_PATH\"" >> ~/.zshrc
source ~/.zshrc
```

### 4. Configure your research interests

Edit `config.yaml` in the repo root to set your vault path, research domains, target journals, and priority authors. The file is read directly by the scripts — no copying needed.

Manually replace `<PATH_TO_YOUR_OBSIDIAN_VAULT>` with your actual vault path:

```yaml
vault_path: "<PATH_TO_YOUR_OBSIDIAN_VAULT>"

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

Manually set `<PATH_TO_YOUR_OBSIDIAN_VAULT>` before running (or skip the first line if you already set `OBSIDIAN_VAULT_PATH` in step 3):

```bash
OBSIDIAN_VAULT_PATH="<PATH_TO_YOUR_OBSIDIAN_VAULT>"
cd "$OBSIDIAN_VAULT_PATH"

```

---

## Usage

### Using Within Claude

```
claude
/start-literature-research --start 20260225 --end 20260304
```

Dates are `YYYYMMDD`, both inclusive. The note is saved to:

```
$OBSIDIAN_VAULT_PATH/literature_research/20260225_20260304_literature_research.md
```

### Using Outside of Claude

All commands must be run from the repo root (where `pixi.toml` lives):

```bash
cd /path/to/evilread-literature-research
OBSIDIAN_VAULT_PATH="<PATH_TO_YOUR_OBSIDIAN_VAULT>"
START_DATE=20250611
END_DATE=20250625
```

**Step 1 — Search papers and save results to JSON:**

```bash
pixi run python start-literature-research/scripts/search_papers.py \
  --output /tmp/results.json \
  --start ${START_DATE} --end ${END_DATE}
```

Optional flags for `search_papers.py`:

```bash
# arXiv + bioRxiv only, skip PubMed
pixi run python start-literature-research/scripts/search_papers.py \
  --output /tmp/results.json \
  --start ${START_DATE} --end ${END_DATE} \
  --skip-pubmed 

# Use a custom config file
pixi run python start-literature-research/scripts/search_papers.py \
  --config /path/to/custom_config.yaml \
  --output /tmp/results.json \
  --start ${START_DATE} --end ${END_DATE}
```

**Step 2 — Generate the Obsidian note from the JSON:**

```bash
pixi run python start-literature-research/scripts/generate_note.py \
  --input /tmp/results.json \
  --output ${OBSIDIAN_VAULT_PATH}/literature_research/${START_DATE}_${END_DATE}_literature_research.md
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
evilread-literature-research/
├── README.md
├── pixi.toml                          # Python dependency spec
├── config.yaml                        # Public config template — edit this
├── config.local.yaml                  # (gitignored) Personal override
└── start-literature-research/
    ├── skill.md                       # Claude Code skill definition
    └── scripts/
        ├── search_papers.py           # arXiv / bioRxiv / PubMed search + scoring
        └── generate_note.py           # Obsidian note generation
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
         |
         v
6. Deduplicate (DOI first, then normalized title)
7. Score each paper
         |
         v
8. Bucket into Must-Read / High / Moderate / Low / Priority Authors
         |
         v
9. Claude writes the Obsidian note + overview paragraph
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

---

## Acknowledgments

- [arXiv](https://arxiv.org/) — open-access preprint platform
- [bioRxiv](https://www.biorxiv.org/) / [medRxiv](https://www.medrxiv.org/) — life sciences preprint servers
- [PubMed](https://pubmed.ncbi.nlm.nih.gov/) — NCBI biomedical literature database
- [Claude Code](https://claude.ai/claude-code) — AI-assisted development environment
- [Obsidian](https://obsidian.md/) — knowledge management tool
- [Original repo](https://github.com/juliye2025/evil-read-arxiv) - inspiration source
 
## License

MIT License
