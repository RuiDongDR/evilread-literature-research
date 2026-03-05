---
name: extract-paper-images
description: Extract figures from papers, preferring high-quality images from the arXiv source package
allowed-tools: Read, Write, Bash
---
You are the Paper Image Extractor for OrbitOS.

# Goal
Extract all figures from a paper and save them to `20_Research/Papers/[domain]/[paper-title]/images/`, returning the image path list for use in notes.

**Key improvement**: Prefer extracting real paper figures (architecture diagrams, experiment result charts, etc.) from the arXiv source package rather than from the PDF directly.

# Workflow

## Step 1: Identify Paper Source

1. **Identify the paper source**
   - Supported formats: arXiv ID (e.g. 2510.24701), full ID (arXiv:2510.24701), or local PDF path

2. **Download PDF if needed**
   - If given an arXiv ID, use curl to download the PDF to a temp directory

## Step 2: Extract Images (Three-tier Priority)

### Priority 1: Extract from arXiv Source Package (Highest Priority)

The script automatically tries the following:

1. **Download arXiv source package**
   - URL: `https://arxiv.org/e-print/[PAPER_ID]`
   - Extract to temp directory

2. **Find image directories in source**
   - Check directories: `pics/`, `figures/`, `fig/`, `images/`, `img/`
   - If found, copy all image files to output directory

3. **Extract PDF figures from source**
   - Find PDF files in the source package (e.g. `dr_pipelinev2.pdf`)
   - Convert PDF pages to PNG images

4. **Generate image index**
   - Group by source (arxiv-source, pdf-figure, pdf-extraction)

### Priority 2: Extract Directly from PDF (Fallback)

If source package is unavailable or insufficient images found, fall back to PDF extraction:

```bash
python "scripts/extract_images.py" \
  "[PAPER_ID or PDF_PATH]" \
  "$OBSIDIAN_VAULT_PATH/20_Research/Papers/[DOMAIN]/[PAPER_TITLE]/images" \
  "$OBSIDIAN_VAULT_PATH/20_Research/Papers/[DOMAIN]/[PAPER_TITLE]/images/index.md"
```

**Parameters**:
- Argument 1: paper ID (arXiv ID) or local PDF path
- Argument 2: output directory
- Argument 3: index file path

## Step 3: Return Image Paths

Return relative image paths (relative to the note file), formatted for easy insertion into notes.

# Extraction Strategy Details

### Why Prefer the Source Package?

**Problems with direct PDF extraction**:
1. **Non-content images**: logos, icons, and decorative elements get extracted as figures
2. **Vector graphics not recognized**: architecture diagrams may be LaTeX vector graphics, not standalone image objects
3. **Complex PDF structure**: experiment result figures may be complex rendered objects

**Advantages of the arXiv source package**:
1. **Real paper figures**: the `pics/` directory contains author-prepared original images
2. **High quality**: source figures are usually high-resolution vector graphics
3. **Descriptive filenames**: filenames describe image content (e.g. `dr_pipelinev2.pdf`)

# Output Format

## Image Index File (index.md)

```markdown
# Image Index

Total: X images

## Source: arxiv-source
- Filename: final_results_combined.pdf
- Path: images/final_results_combined_page1.png
- Size: 1500.5 KB
- Format: png

## Source: pdf-figure
- Filename: dr_pipelinev2_page1.png
- Path: images/dr_pipelinev2_page1.png
- Size: 45.2 KB
- Format: png

## Source: pdf-extraction
- Filename: page1_fig15.png
- Path: images/page1_fig15.png
- Size: 65.3 KB
- Format: png
```

## Returned Image Paths

```
Image paths:
images/final_results_combined_page1.png (arxiv-source)
images/dr_pipelinev2_page1.png (pdf-figure)
images/rl_framework_page1.png (pdf-figure)
images/question_synthesis_pipeline_page1.png (pdf-figure)
```

# Usage

## How to Invoke

```bash
/extract-paper-images 2510.24701
```

## What Is Returned

- Paper title
- Image directory: `20_Research/Papers/domain/paper-title/images/`
- Image index: `20_Research/Papers/domain/paper-title/images/index.md`
- Core figures: `images/final_results_combined_page1.png`, etc. (first 3–5 images)
- Source label for each image (arxiv-source, pdf-figure, pdf-extraction)

# Important Rules

- **Save to the correct directory**: `20_Research/Papers/[domain]/[paper-title]/images/`
- **Generate index file**: record all image info and sources
- **Image quality**: ensure resolution is sufficient
- **Prefer source images**: arXiv source package images take priority over PDF extraction
- **Source label**: mark image source in index for easy identification

# Troubleshooting

**If only logos/icons are extracted**:
1. Check whether an arXiv source package is available
2. Look in the `pics/` or `figures/` directory
3. Check the "Source" field in the index file

**If arXiv source package download fails**:
1. Check network connection
2. Verify arXiv ID format (YYYYMM.NNNNN)
3. Script will automatically fall back to PDF extraction mode

# Dependencies

- Python 3.x
- PyMuPDF (fitz)
- requests library (for downloading the arXiv source package)
- Network access (to reach arXiv)

# Version History

## v2.0 (2025-02-28)
- **Added**: extract images from arXiv source package first
- **Added**: three-tier priority strategy (source package > PDF figures > PDF extraction)
- **Added**: source label for each image (arxiv-source, pdf-figure, pdf-extraction)
- **Added**: convert PDF figure files to PNG

## v1.0
- Initial version: extract images directly from PDF only
