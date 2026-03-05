---
name: paper-analyze
description: Deep analysis of a single paper — generate a detailed, figure-rich note and evaluation
allowed-tools: Read, Write, Bash, WebFetch
---
You are the Paper Analyzer for OrbitOS.

# Goal
Perform a deep analysis of a specific paper, generate a comprehensive note, evaluate quality and value, and update the knowledge base.

# Workflow

## Step 0: Initialize Environment

```bash
# Create working directory
mkdir -p /tmp/paper_analysis
cd /tmp/paper_analysis

# Set variables (read from OBSIDIAN_VAULT_PATH env var, or ask user)
PAPER_ID="[PAPER_ID]"
VAULT_ROOT="${OBSIDIAN_VAULT_PATH}"
PAPERS_DIR="${VAULT_ROOT}/20_Research/Papers"
```

## Step 1: Identify the Paper

### 1.1 Parse Paper Identifier

Accepted input formats:
- arXiv ID: "2402.12345"
- Full ID: "arXiv:2402.12345"
- Paper title: "Paper Title"
- File path: direct path to an existing note

### 1.2 Check for Existing Notes

1. **Search for existing notes**
   - Search `20_Research/Papers/` by arXiv ID
   - Search by title match
   - If found, read the note

2. **Read paper note**
   - If found, return full content

## Step 2: Fetch Paper Content

### 2.1 Download PDF and Source

```bash
# Download PDF
curl -L "https://arxiv.org/pdf/[PAPER_ID]" -o /tmp/paper_analysis/[PAPER_ID].pdf

# Download source package (contains TeX and figures)
curl -L "https://arxiv.org/e-print/[PAPER_ID]" -o /tmp/paper_analysis/[PAPER_ID].tar.gz
tar -xzf /tmp/paper_analysis/[PAPER_ID].tar.gz -C /tmp/paper_analysis/
```

### 2.2 Extract Paper Metadata

```bash
# Fetch arXiv page
curl -s "https://arxiv.org/abs/[PAPER_ID]" > /tmp/paper_analysis/arxiv_page.html

# Extract key info (general regex, works for any paper)
TITLE=$(grep -oP '<title>\K[^<]*' /tmp/paper_analysis/arxiv_page.html | head -1)
AUTHORS=$(grep -oP 'citation_author" content="\K[^"]*' /tmp/paper_analysis/arxiv_page.html | paste -sd ', ')
DATE=$(grep -oP 'citation_date" content="\K[^"]*' /tmp/paper_analysis/arxiv_page.html | head -1)
```

### 2.3 Read TeX Source Content

```bash
# Read section content
cat /tmp/paper_analysis/1-introduction.tex
cat /tmp/paper_analysis/2-methods.tex
cat /tmp/paper_analysis/3-experiments.tex
```

### 2.4 Fetch from arXiv API

1. **Get paper metadata**
   - Use WebFetch on the arXiv API
   - Query parameter: `id_list=[arXiv ID]`
   - Extract: title, authors, abstract, publication date, categories, links, PDF link

2. **Fetch PDF content and figures**
   - Use WebFetch to get the PDF
   - **Important**: extract all figures from the paper
   - Save to `20_Research/Papers/[domain]/[paper-title]/images/`
   - Generate image index: `images/index.md`

## Step 3: Deep Analysis

### 3.1 Analyze the Abstract

1. **Extract key concepts**
   - Identify the main research problem
   - List key terms and concepts
   - Note the technical domain

2. **Summarize research goals**
   - What problem is being solved?
   - What is the proposed solution approach?
   - What are the main contributions?

### 3.2 Analyze Methodology

1. **Identify the core method**
   - Main algorithm or approach
   - Technical innovations
   - Differences from existing methods

2. **Analyze the method structure**
   - Method components and their relationships
   - Data flow or processing pipeline
   - Key parameters or configurations

3. **Evaluate method novelty**
   - What is unique about this method?
   - How does it compare to existing methods?
   - What are the key innovations?

### 3.3 Analyze Experiments

1. **Extract experimental setup**
   - Datasets used
   - Baseline methods for comparison
   - Evaluation metrics
   - Experimental environment

2. **Extract results**
   - Key performance numbers
   - Comparison with baselines
   - Ablation studies (if any)

3. **Evaluate experimental rigor**
   - Are experiments comprehensive?
   - Is evaluation fair?
   - Are baselines appropriate?

### 3.4 Generate Insights

1. **Research value**
   - Theoretical contributions
   - Practical applications
   - Domain impact

2. **Limitations**
   - Limitations mentioned in the paper
   - Potential weaknesses
   - What assumptions might not hold?

3. **Future work**
   - Future research suggested by authors
   - Natural extensions
   - Room for improvement

4. **Comparison with related work**
   - Search for related prior papers
   - How does this compare to similar papers?
   - What gap does it fill?
   - Which research thread does it belong to?

## Step 3b: Copy Figures and Generate Index

```bash
# Copy figures to target location
cp /tmp/paper_analysis/*.{pdf,png,jpg,jpeg} "PAPERS_DIR/[DOMAIN]/[PAPER_TITLE]/images/" 2>/dev/null

# List copied content
ls "PAPERS_DIR/[DOMAIN]/[PAPER_TITLE]/images/"
```

## Step 4: Generate Comprehensive Paper Note

### 4.1 Determine Note Path and Domain

```bash
# Determine domain from paper content
# Inference rules:
# - If mentions "agent/swarm/multi-agent/orchestration" → Agents
# - If mentions "vision/visual/image/video" → Multimodal
# - If mentions "reinforcement learning/RL" → RL-Agents
# - If mentions "language model/LLM/MoE" → LLMs
# - Otherwise → Other

PAPERS_DIR="${VAULT_ROOT}/20_Research/Papers"
DOMAIN="[inferred domain]"
PAPER_TITLE="[paper title, spaces replaced with underscores]"
NOTE_PATH="${PAPERS_DIR}/${DOMAIN}/${PAPER_TITLE}.md"
IMAGES_DIR="${PAPERS_DIR}/${DOMAIN}/${PAPER_TITLE}/images"
INDEX_PATH="${IMAGES_DIR}/index.md"
```

### 4.2 Generate Note Using Python Script

```bash
python "scripts/generate_note.py" \
  --paper-id "[PAPER_ID]" \
  --title "[paper title]" \
  --authors "[authors]" \
  --domain "[domain]"
```

### 4.3 Note Structure

```markdown
---
date: "YYYY-MM-DD"
paper_id: "arXiv:XXXX.XXXXX"
title: "Paper Title"
authors: "Author List"
domain: "[domain name]"
tags:
  - paper-note
  - [domain-tag]
  - [method-tag-no-spaces]  # tag names cannot contain spaces; use hyphens instead
  # e.g.: "Agent Swarm" → "Agent-Swarm"
  #       "Visual Agentic" → "Visual-Agentic"
  - [related-paper-1]
  - [related-paper-2]
quality_score: "[X.X]/10"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
status: analyzed
---

# [Paper Title]

## Core Information
- **Paper ID**: arXiv:XXXX.XXXXX
- **Authors**: [Author 1, Author 2, Author 3]
- **Affiliation**: [inferred from authors or paper]
- **Published**: YYYY-MM-DD
- **Venue**: [inferred from categories]
- **Links**: [arXiv](link) | [PDF](link)
- **Citations**: [if available]

## Abstract

### Original Abstract
[paper's original English abstract]

### Key Takeaways
- **Research background**: [current state of the field and existing problems]
- **Research motivation**: [why this research is needed]
- **Core method**: [one-sentence summary of the main approach]
- **Main results**: [most important experimental results]
- **Research significance**: [contribution to the field]

## Research Background and Motivation

### Field Overview
[Detailed description of the current state of this research area]

### Limitations of Existing Methods
[In-depth analysis of problems with existing approaches]

### Research Motivation
[Explain why this research is needed]

## Research Problem

### Core Research Question
[Clear, accurate description of the core problem the paper addresses]

## Method Overview

### Core Idea
[Explain the core idea of the method in plain language]

### Method Framework

#### Overall Architecture
[Describe the overall architecture, including main components and their relationships]

**Architecture diagram selection principles**:
1. **Prefer existing figures from the paper** — if the paper PDF contains an architecture/flow/method diagram, insert it directly
2. **Create Canvas only if no suitable figure exists** — use JSON Canvas only when the paper lacks a suitable architecture diagram

**Option 1: Insert figure from paper (preferred)**
```
![Architecture|800](images/pageX_figY.pdf)

> Figure 1: [architecture description, including what each part means and how they relate]
```
**Note**: image filename must match the actual file (images extracted from arXiv are usually `.pdf`)

**Option 2: Create Canvas architecture diagram (when paper has no figure)**
Call the `json-canvas` skill to create a `.canvas` file, then embed it:
```
![[PaperTitle_Architecture.canvas|1200|400]]
```

Canvas creation steps:
1. Call the `json-canvas` skill
2. Use `--create --file "path/architecture.canvas"` argument
3. Create nodes and connections, use different colors for different levels
4. Embed reference in markdown after saving

**Text diagram example** (last resort when no image or Canvas is possible):
```
Input → [Module 1] → [Module 2] → [Module 3] → Output
          ↓             ↓             ↓
       [Submodule]  [Submodule]  [Submodule]
```

#### Detailed Module Description

**Module 1: [Module Name]**
- **Function**: [main function of this module]
- **Input**: [input data/information]
- **Output**: [output data/information]
- **Processing flow**:
  1. [step 1 detailed description]
  2. [step 2 detailed description]
  3. [step 3 detailed description]
- **Key techniques**: [key techniques or algorithms used]
- **Math formulas**: [important formulas if any]
  ```
  [formula content]
  ```

**Module 2: [Module Name]**
[similar format]

**Module 3: [Module Name]**
[similar format]

### Method Architecture Diagram
[Choose the most appropriate way to show the architecture]

**Selection principles**:
1. **Prefer paper architecture figures** — insert directly if suitable method/flow/system diagrams exist
2. **Create Canvas only if no figure** — use JSON Canvas only when needed

**Option 1: Insert paper figure (preferred)**
```
![Architecture|800](images/pageX_figY.pdf)

> Figure 1: [architecture description]
```

**Option 2: Create Canvas (when paper has no figure)**
```
![[PaperTitle_Architecture.canvas|1200|400]]
```

**Note**: Canvas is supplementary only — do not replace existing paper figures.

## Experimental Results

### Experimental Goal
[What this experiment aims to validate]

### Datasets

#### Dataset Statistics

| Dataset | Samples | Feature Dims | Classes | Data Type |
|---------|---------|--------------|---------|-----------|
| Dataset1 | XK | Y | Z | [type] |
| Dataset2 | XK | Y | Z | [type] |

### Experimental Setup

#### Baseline Methods
[List all baseline methods with brief descriptions]

#### Evaluation Metrics
[List all evaluation metrics and explain each]

#### Experimental Environment

#### Hyperparameter Settings

### Main Results

#### Main Experiment Results

| Method | Dataset1-Metric1 | Dataset1-Metric2 | Dataset2-Metric1 | Dataset2-Metric2 | Avg Rank |
|--------|------------------|------------------|------------------|------------------|----------|
| Baseline1 | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | N |
| Baseline2 | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | N |
| **This paper** | **X.X±Y.Y** | **X.X±Y.Y** | **X.X±Y.Y** | **X.X±Y.Y** | **N** |

> Note: ± shows standard deviation; **bold** = best result

#### Result Analysis
[Detailed analysis of main experiment results]

### Ablation Study

#### Study Design
[Design rationale for the ablation study]

#### Ablation Results and Analysis

### Experiment Result Figures
[Insert experiment result figures from the paper]

![Experiment results|800](images/experiment_results.pdf)

> Figure 2: [figure description]
**Note**: image filename must match actual file (arXiv images are usually `.pdf`)

## In-Depth Analysis

### Research Value Assessment

#### Theoretical Contributions
- **Contribution 1**: [detailed description]
  - Innovation: [type of innovation/new method/new perspective]
  - Academic value: [value to the research community]
  - Scope of impact: [affected research areas]

- **Contribution 2**: [detailed description]
  [similar format]

#### Practical Application Value
- **Use case 1**: [scenario description]
  - Applicability: [how well the method fits this scenario]
  - Advantage: [advantage over existing solutions]
  - Potential impact: [likely impact]

- **Use case 2**: [scenario description]
  [similar format]

#### Domain Impact
- **Short-term**: [near-term likely impact]
- **Mid-term**: [mid-term likely impact]
- **Long-term**: [long-term likely impact]
- **Potential shift**: [possible paradigm changes]

### Method Advantages

#### Advantage 1: [Advantage Name]
- **Description**: [detailed description]
- **Technical basis**: [technical foundation of this advantage]
- **Experimental validation**: [how experiments validate this]
- **Comparative analysis**: [how much better than existing methods]

#### Advantage 2: [Advantage Name]
[similar format]

#### Advantage 3: [Advantage Name]
[similar format]

### Limitations Analysis

#### Limitation 1: [Limitation Name]
- **Description**: [detailed description]
- **Manifestation**: [how it appears in practice]
- **Root cause**: [fundamental cause]
- **Impact**: [effect on practical applications]
- **Possible solutions**: [how to mitigate or resolve]

#### Limitation 2: [Limitation Name]
[similar format]

### Applicability

#### Suitable Scenarios
- **Scenario 1**: [scenario description]
  - Why it fits: [reason]
  - Expected effect: [what to expect]
  - Notes: [things to watch out for]

- **Scenario 2**: [scenario description]
  [similar format]

#### Unsuitable Scenarios
- **Scenario 1**: [scenario description]
  - Why it doesn't fit: [reason]
  - Alternative: [suggested alternative]

- **Scenario 2**: [scenario description]
  [similar format]

## Comparison with Related Papers

### Selection Criteria
[Why these papers were chosen for comparison]

### [[Related Paper 1]] - [Paper Title]

#### Basic Info
- **Authors**: [authors]
- **Published**: [date]
- **Venue**: [venue]
- **Core method**: [one-sentence summary]

#### Method Comparison
| Dimension | Related Paper 1 | This Paper |
|-----------|----------------|------------|
| Core idea | [description] | [description] |
| Technical approach | [description] | [description] |
| Key components | [description] | [description] |
| Innovation level | [description] | [description] |

#### Performance Comparison
| Dataset | Metric | Related Paper 1 | This Paper | Improvement |
|---------|--------|----------------|------------|-------------|
| Dataset1 | Metric1 | X.X | Y.Y | +Z.Z% |
| Dataset2 | Metric2 | X.X | Y.Y | +Z.Z% |

#### Relationship Analysis
- **Relationship type**: [improves / extends / compares / follows]
- **Improvements**: [what this paper improves over that one]
- **Advantages**: [advantages of this paper's method]
- **Disadvantages**: [disadvantages of this paper's method]
- **Complementarity**: [whether the two methods complement each other]

### [[Related Paper 2]] - [Paper Title]
[similar format]

### [[Related Paper 3]] - [Paper Title]
[similar format]

### Comparison Summary
[Summary of all comparison papers]

## Technical Lineage

### Research Thread
This paper belongs to [research thread name]. Core characteristics of this thread:
- Characteristic 1: [description]
- Characteristic 2: [description]
- Characteristic 3: [description]

### Development History
```
[Milestone 1] → [Milestone 2] → [Milestone 3] → [This paper] → [Future direction]
      ↑               ↑               ↑               ↑
  [Paper A]       [Paper B]       [Paper C]       [This paper]
```

### Position in the Research Thread
- **Building on**: [what prior work this inherits from]
- **Enabling**: [what foundation this provides for future work]
- **Key node**: [why this is a key node in the thread]

### Specific Sub-direction
This paper focuses on [specific sub-direction]. Key research focuses:
- Focus 1: [description]
- Focus 2: [description]

### Related Work Map
[Use text or diagrams to show relationships with related work]

## Future Work

### Author-Suggested Future Work
1. **Suggestion 1**: [author's suggestion]
   - Feasibility: [whether feasible]
   - Value: [potential value]
   - Difficulty: [implementation difficulty]

2. **Suggestion 2**: [author's suggestion]
   [similar format]

### Analysis-Based Future Directions
1. **Direction 1**: [direction description]
   - Motivation: [why this direction is worth researching]
   - Possible approaches: [possible research methods]
   - Expected outcomes: [likely results]
   - Challenges: [challenges to face]

2. **Direction 2**: [direction description]
   [similar format]

3. **Direction 3**: [direction description]
   [similar format]

### Improvement Suggestions
[Specific improvement suggestions for the method in this paper]
1. **Improvement 1**: [improvement description]
   - Current problem: [existing issue]
   - Improvement approach: [how to improve]
   - Expected effect: [expected outcome]

2. **Improvement 2**: [improvement description]
   [similar format]

## My Overall Assessment

### Value Score

#### Overall Score
**[X.X]/10** — [brief rationale]

#### Dimension Scores

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Innovation | [X]/10 | [detailed rationale] |
| Technical quality | [X]/10 | [detailed rationale] |
| Experimental completeness | [X]/10 | [detailed rationale] |
| Writing quality | [X]/10 | [detailed rationale] |
| Practicality | [X]/10 | [detailed rationale] |

### Key Points

#### Technical points worth attention

#### Parts needing deeper understanding

## My Notes

%% User can add personal reading notes here %%

## Related Papers

### Directly Related
- [[Related Paper 1]] — [relationship: improves/extends/compares/etc.]
- [[Related Paper 2]] — [relationship]

### Background Related
- [[Background Paper 1]] — [relationship]
- [[Background Paper 2]] — [relationship]

### Follow-up Work
- [[Follow-up Paper 1]] — [relationship]
- [[Follow-up Paper 2]] — [relationship]

## External Resources
[List links to related videos, blog posts, projects, etc.]

> [!tip] Key Insight
> [Most important insight from the paper, summarized in one sentence]

> [!warning] Notes
> - [Note 1]
> - [Note 2]
> - [Note 3]

> [!success] Recommendation
> ⭐⭐⭐⭐⭐ [Recommendation level and brief reason, e.g.: Strongly recommended! This is a landmark paper in XX field]
```

## Step 5: Update Knowledge Graph

### 5.1 Add or Update Node

1. **Read graph data**
   - File path: `$OBSIDIAN_VAULT_PATH/20_Research/PaperGraph/graph_data.json`

2. **Add or update node for this paper**
   - Include analysis metadata:
     - quality_score
     - tags
     - domain
     - analyzed: true

3. **Create edges to related papers**
   - For each related paper, create an edge
   - Edge types:
     - `improves`: improvement relationship
     - `related`: general relationship
   - Weight: based on similarity (0.3–0.8)

4. **Update timestamp**
   - Set `last_updated` to current date

5. **Save graph**
   - Write updated graph_data.json

```bash
python "scripts/update_graph.py" \
  --paper-id "[PAPER_ID]" \
  --title "[paper title]" \
  --domain "[domain]" \
  --score [score]
```

## Step 6: Display Analysis Summary

### 6.1 Output Format

```markdown
## Paper Analysis Complete!

**Paper**: [[Paper Title]] (arXiv:XXXX.XXXXX)

**Status**: ✅ Detailed note generated
**Note location**: [[20_Research/Papers/domain/YYYY-MM-DD-arXiv-ID.md]]

---

**Overall score**: [X.X/10]

**Dimension scores**:
- Innovation: [X/10]
- Technical quality: [X/10]
- Experimental completeness: [X/10]
- Writing quality: [X/10]
- Practicality: [X/10]

**Highlights**:
- [highlight 1]
- [highlight 2]
- [highlight 3]

**Main advantages**:
- [advantage 1]
- [advantage 2]

**Main limitations**:
- [limitation 1]
- [limitation 2]

**Related papers** (N):
- [[Related Paper 1]] — [relationship]
- [[Related Paper 2]] — [relationship]
- [[Related Paper 3]] — [relationship]

**Research thread**:
This paper belongs to [research thread], focusing on [sub-direction].

---

**Quick actions**:
- Click the note link to view detailed analysis
- Use `/paper-search` to find more related papers
- Open Graph View to see paper relationships
- Based on the analysis, decide whether to study in depth or skip

**Suggestions**:
- [specific suggestion 1 based on analysis]
- [specific suggestion 2 based on analysis]
```

## Important Rules

- **Preserve existing user notes** — do not overwrite manually written notes
- **Use comprehensive analysis** — cover methodology, experiments, and value assessment
- **Write content in English** — translate and explain in English
- **Cite related work** — build connections to the existing knowledge base
- **Objective scoring** — use consistent scoring criteria
- **Update knowledge graph** — maintain relationships between papers
- **Figure-rich** — use all figures from the paper (architecture diagrams, method figures, experiment charts, etc.)
- **Handle errors gracefully** — if one source fails, continue with others
- **Manage token use** — be comprehensive but stay within token limits

## Scoring Criteria

### Score Details (0–10 scale)

**Innovation**:
- 9–10: novel breakthrough, new paradigm
- 7–8: significant improvement or combination
- 5–6: minor contribution, already known or established
- 3–4: incremental improvement
- 1–2: known or established

**Technical quality**:
- 9–10: rigorous methodology, well-reasoned approach
- 7–8: good approach, minor issues
- 5–6: acceptable approach, some problems
- 3–4: problematic approach
- 1–2: poor approach

**Experimental completeness**:
- 9–10: comprehensive experiments, strong baselines
- 7–8: good experiments, adequate baselines
- 5–6: acceptable experiments, partial baselines
- 3–4: limited experiments, weak baselines
- 1–2: poor or no baselines

**Writing quality**:
- 9–10: clear, well-organized
- 7–8: mostly clear, minor issues
- 5–6: understandable, partially unclear
- 3–4: hard to follow, confusing
- 1–2: poor writing

**Practicality**:
- 9–10: high practical impact, directly applicable
- 7–8: good practical potential
- 5–6: moderate practical value
- 3–4: limited practicality, theoretical only
- 1–2: low practicality

### Relationship Type Definitions

- `improves`: clear improvement over related work
- `extends`: extends or builds on related work
- `compares`: direct comparison, may be better/worse in some aspects
- `follows`: follow-up work in the same research thread
- `cites`: citation (if citation data is available)
- `related`: general conceptual relationship

## Error Handling

- **Paper not found**: check ID format, suggest searching
- **arXiv down**: use cache or retry later, note limitations in output
- **PDF parse failure**: fall back to abstract, note limitations
- **Related papers not found**: note lack of context
- **Graph update failure**: continue but skip graph update

## Usage

When the user calls `/paper-analyze [paper ID]`:

### Quick Execution (Recommended)

Use this bash script to run the full flow in one step:

```bash
#!/bin/bash

# Set variables
PAPER_ID="$1"
TITLE="${2:-TBD}"
AUTHORS="${3:-Unknown}"
DOMAIN="${4:-Other}"

# Run full flow
python "scripts/generate_note.py" \
  --paper-id "$PAPER_ID" \
  --title "$TITLE" \
  --authors "$AUTHORS" \
  --domain "$DOMAIN" || \
    echo "Note generation script failed"

# Extract images (call extract-paper-images skill)
# /extract-paper-images "$PAPER_ID" "$DOMAIN" "$TITLE"
```

### Manual Step-by-Step (for Debugging)

#### Step 0: Initialize environment
```bash
mkdir -p /tmp/paper_analysis
cd /tmp/paper_analysis
```

#### Step 1: Identify paper
```bash
find "${VAULT_ROOT}/20_Research/Papers" -name "*${PAPER_ID}*" -type f
```

#### Step 2: Fetch paper content
```bash
# Download PDF and source (see Steps 2.1, 2.2, 2.3)
```

#### Step 3: Copy figures
```bash
/extract-paper-images "$PAPER_ID" "$DOMAIN" "$TITLE"
```

#### Step 4: Generate note
```bash
python "scripts/generate_note.py" \
  --paper-id "$PAPER_ID" \
  --title "$TITLE" \
  --authors "$AUTHORS" \
  --domain "$DOMAIN"
```

#### Step 5: Update graph
```bash
python "scripts/update_graph.py" \
  --paper-id "$PAPER_ID" \
  --title "$TITLE" \
  --domain "$DOMAIN" \
  --score 8.8
```

### Notes

1. **Frontmatter format (important)**: all string values must be in double quotes
   ```yaml
   ---
   date: "YYYY-MM-DD"
   paper_id: "arXiv:XXXX.XXXXX"
   title: "Paper Title"
   authors: "Author List"
   domain: "[domain name]"
   quality_score: "[X.X]/10"
   created: "YYYY-MM-DD"
   updated: "YYYY-MM-DD"
   status: analyzed
   ---
   ```
   **Obsidian requires strict YAML format — missing quotes will break frontmatter display!**

2. **Image paths**: use relative paths `images/xxx` (no extension needed; Obsidian auto-detects)
   - **Important**: images extracted from arXiv are usually `.pdf` format; Obsidian can display PDF images directly
   - Use actual filenames, e.g. `images/loss_curve.pdf` or `images/figure1.png`
3. **Wikilinks**: use `[[Paper Title]]` format
4. **Domain inference**: automatically infer from paper content
5. **Related papers**: reference `[[Related Paper]]` in notes; the graph will auto-create edges

## Key Features

**Figure-rich**: use all figures from the paper
- **Save to correct location**: `20_Research/Papers/[domain]/[paper-title]/images/`
- **Image index**: generate `images/index.md` indexing all figures
- **Difference from start-my-day**: paper-analyze is for deep analysis of a single paper
- **Comprehensive analysis**: cover all sections, figure-rich
