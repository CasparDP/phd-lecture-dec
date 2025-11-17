# Main Scipts

**Purpose:** Uses local LLM (Ollama) to match safeguard investigation case titles to SIC/NAICS industry codes.

**What it does:**

- Loads the SIC-NAICS crosswalk from Census Bureau data
- Extracts cleaned investigation titles from the previous step
- Performs TF-IDF text similarity to find top 10 candidate industries per case
- Uses local Ollama LLM (`gpt-oss:20b`) to reason about the best industry match
- Validates LLM output using Pydantic models
- Returns SIC and NAICS codes with reasoning

**Output:** `data-prep/safeguard_matches.csv` - Matched investigation IDs with best SIC/NAICS codes and reasoning.

**Prerequisites:**

- Ollama must be running locally with the `gpt-oss:20b` model pulled
- `data-prep/1987_sic_to_1997_naics.xls` (from `naics_sic_xwalk_DL.R`)

**Dependencies:** `ollama`, `pandas`, `sklearn`, `pydantic`

---

### 4. `jones.R`

**Purpose:** Calculates discretionary accruals (earnings management measure) using the Jones (1991) model on Compustat financial data.

**What it does:**

- Connects to WRDS (Wharton Research Data Services) using credentials from `secrets.csv`
- Downloads US company information and financial statement data (Compustat funda)
- Computes total accruals using the Jones definition: `((ΔCurrent Assets - ΔCash) - (ΔCurrent Liabilities - ΔDebt) - Depreciation) / Lagged Total Assets`
- Also computes alternative accrual measures (income-based) and control variables (ΔRevenue, PPE, ROA)
- Filters to US firms only (excludes financial firms: SIC 6000-6999)
- Creates SIC sector codes at different levels (2, 3, and 4-digit)

**Output:** `data-prep/jones_residuals.csv` - Firm-year panel with accruals measures, ready for event study analysis.

**Prerequisites:**

- Valid WRDS credentials in `secrets.csv` (columns: `user`, `pass`)
- PostgreSQL connection to WRDS server
- `load_libraries.R` dependencies

**Dependencies:** `RPostgres`, `tidyverse`, `duckdb`

---

### 5. `phd-lecture-analyses.R`

**Purpose:** Performs the final event study analysis linking import relief investigations to firm earnings management.

**What it does:**

- Loads cleaned investigation data with matched NAICS codes
- Loads firm accrual data from the Jones model
- Creates treatment cohorts: firms in industries affected by safeguard investigations
- Creates control cohorts: firms in other industries during the same period
- Implements a panel structure with ±6 year windows around each investigation
- Constructs "time" variable measuring years before/after investigation
- Prepares data for regression analysis to test whether treated firms manage earnings differently

**Output:** Formatted panel dataset for regression analysis (used in lecture materials and paper summaries)

**Dependencies:** `load_libraries.R`, `safeguard_matches.csv`, `jones_residuals.csv`, `duckdb`

---

### 6. `report_to_docling.py` (Auxiliary)

**Purpose:** Converts PDF research papers into structured markdown summaries using local LLM.

**What it does:**

- Reads PDF files from `papers/` directory
- Uses Docling library to convert PDFs to high-quality markdown
- Caches markdown to avoid re-processing
- Sends markdown content to local Ollama LLM for summarization
- Extracts key sections: research idea, contribution, theory, hypothesis, design, results
- Generates Quarto (`.qmd`) formatted summaries with frontmatter

**Output:** Quarto markdown files in `paper_summaries/` with structured paper summaries.

**Prerequisites:** Ollama running locally with an LLM model

**Dependencies:** `ollama`, `docling`, `pathlib`, `tiktoken`

---

## Recommended Running Order

**For initial setup:**

1. `load_libraries.R` - Install and configure R environment
2. `naics_sic_xwalk_DL.R` - Download industry crosswalk

**For data pipeline (sequentially):**

1. `get_data.py` - Scrape USITC investigations
2. `select_cases.R` - Filter and clean investigations
3. `industry_match_chat.py` - Match industries with LLM
4. `jones.R` - Calculate earnings management measures
5. `phd-lecture-analyses.R` - Run final event study analysis

**Optional:**

- `report_to_docling.py` - Summarize research papers (runs independently)
- `etable-setup.R` - Used within other scripts for table formatting

---

## Data Flow

```text
WRDS (Compustat) ──┐
                   ├──> jones.R ──> jones_residuals.csv ──┐
                   │                                       │
                   └────────────────────────────────────────┤
                                                            │
USITC Website ──> get_data.py ──> usitc_import_injury.csv
                                 │
                                 ├──> select_cases.R ──> cleaned_usitc_import_injury.csv
                                 │                       │
                                 │                       ├──> llm_usitc_safeguards_input.csv
                                 │                       │
                                 └───────────────────────┼──> industry_match_chat.py ──> safeguard_matches.csv
                                                         │
                                                         └──> phd-lecture-analyses.R ──> Event Study Panel Data

Census Bureau ──> naics_sic_xwalk_DL.R ──> 1987_sic_to_1997_naics.xls ──> industry_match_chat.py
```

# Research Paper Summarizer - Map-Reduce Workflow

## Overview

This tool converts research papers (PDFs) into structured academic summaries using a fully local map-reduce approach. The system runs entirely on your machine using Ollama—no external APIs, no rate limits, complete privacy.

## Quick Start

### 1. Start Ollama

```bash
ollama serve
```

### 2. Process a Paper

```bash
# Basic usage
poetry run python data-prep/Scripts/report_to_docling.py papers/my_paper.pdf --map-reduce

# With specific model
poetry run python data-prep/Scripts/report_to_docling.py papers/my_paper.pdf --map-reduce --model granite4:latest
```

Output: `paper_summaries/my_paper/my_paper_summary.qmd`

## How It Works

```
PDF Input
    ↓
[PDF → Markdown] Docling extracts text
    ↓
[Split] TextSplitterAgent chunks by paragraphs (~4000 chars)
    ↓
[Map] MapAgent processes each chunk
    • Extracts: Main Claims, Methodology, Evidence, Context
    ↓
[Reduce] ReduceAgent synthesizes all outputs
    • Creates: Cohesive academic summary
    ↓
Quarto File Output
```

## Agent Classes

### TextSplitterAgent

Splits documents intelligently by paragraph boundaries while respecting chunk size targets.

**Method**: `run(full_text, chunk_size_target=4000) -> List[str]`

### MapAgent

Processes each chunk to extract structured information using `map_prompt.txt` template.

**Method**: `run(text_chunk) -> str`

**Extracts**:

- Main claims and arguments
- Key methodology details
- Core evidence and results
- Important context and definitions

### ReduceAgent

Synthesizes all chunk extractions into a final academic summary using `reduce_prompt.txt` template.

**Method**: `run(synthesis_document) -> str`

**Creates**:

- Research question overview
- Methodology summary
- Key findings
- Implications and conclusions

### OrchestratorAgent

Coordinates the complete workflow from input text to final summary.

**Method**: `run(full_text) -> str`

## Configuration

### Change Model

Edit `report_to_docling.py` (line ~23):

```python
OLLAMA_MODEL = "granite4:latest"  # Change to your preferred model
```

Available models (after `ollama pull <model>`):

- `granite4:latest` (default)
- `deepseek-r1:8b`
- `llama3`
- `mistral`

### Customize Extraction

Edit `map_prompt.txt` to change what gets extracted from each chunk.

Current extraction format:

```
1. Main Claims: ...
2. Key Methodology: ...
3. Core Evidence/Results: ...
4. Important Context/Definitions: ...
```

### Customize Synthesis

Edit `reduce_prompt.txt` to change how the final summary is structured.

Current synthesis format:

```
Research Question → Methodology → Findings → Implications
```

### Adjust Chunk Size

Edit the `chunk_size_target` parameter in `TextSplitterAgent.run()`:

```python
chunks = text_splitter.run(full_text, chunk_size_target=4000)  # Change this
```

## Key Files

| File                    | Purpose                                |
| ----------------------- | -------------------------------------- |
| `report_to_docling.py`  | Main script with integrated map-reduce |
| `map_prompt.txt`        | Template for chunk extraction          |
| `reduce_prompt.txt`     | Template for synthesis                 |
| `orchestrator_logic.py` | Standalone test script (optional)      |

## Examples

```bash
# Process single paper
poetry run python data-prep/Scripts/report_to_docling.py papers/Jones-1991.pdf --map-reduce

# Process with faster model
poetry run python data-prep/Scripts/report_to_docling.py papers/Jones-1991.pdf --map-reduce --model mistral

# Test standalone (uses dummy data)
poetry run python data-prep/Scripts/orchestrator_logic.py
```

## Troubleshooting

**Model not found**

```bash
ollama pull granite4:latest
```

**Connection refused**

```bash
# Ensure Ollama is running
ollama serve
```

**Slow processing**

- Normal for large models. Use smaller models (7B) for speed
- Or reduce chunk size for fewer API calls

**Poor quality output**

- Try a larger model (13B or 20B)
- Customize `map_prompt.txt` and `reduce_prompt.txt` for your domain

## Performance

| Model Size     | Speed                 | Quality   | Memory |
| -------------- | --------------------- | --------- | ------ |
| 7B (mistral)   | Fast (10-20s/chunk)   | Good      | 8 GB   |
| 13B (granite4) | Medium (30-60s/chunk) | Better    | 16 GB  |
| 20B+ (gpt-oss) | Slow (60-120s/chunk)  | Excellent | 24+ GB |

## Advantages

✅ **Fully Local** - No external API calls
✅ **Private** - Documents never leave your machine
✅ **Offline** - Works without internet
✅ **Free** - No API costs
✅ **Customizable** - Full control over prompts and models
✅ **Synchronous** - Simple, readable code
