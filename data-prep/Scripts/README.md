# Main Scripts

## 1. `get_data.py`

**Purpose:** Scrape USITC safeguard investigations data.

**What it does:**

- Crawls the USITC website for import injury/safeguard investigations.
- Extracts case identifiers, titles, dates, industry descriptions, and basic metadata.
- Saves a raw, machine-readable dataset for further cleaning.

**Output:** `data-prep/usitc_import_injury.csv`

**Dependencies:** `requests`, `beautifulsoup4`, `pandas`

---

## 2. `select_cases.R`

**Purpose:** Clean and filter USITC investigations to the sample used in the lecture.

**What it does:**

- Reads `usitc_import_injury.csv`.
- Applies sample restrictions (time window, safeguard-type cases, data completeness).
- Cleans and standardizes titles, dates, and industry descriptions.
- Prepares LLM input prompts for industry matching.

**Outputs:**

- `data-prep/cleaned_usitc_import_injury.csv`
- `data-prep/llm_usitc_safeguards_input.csv`

**Dependencies:** `tidyverse`, `readr`, `dplyr`

---

## 3. `industry_match_chat.py`

**Purpose:** Use a local LLM (Ollama) to match safeguard investigation titles to SIC/NAICS industry codes.

**What it does:**

- Loads the SIC–NAICS crosswalk from Census Bureau data.
- Reads cleaned investigation titles and LLM input prompts.
- Performs TF–IDF text similarity to find top candidate industries per case.
- Uses a local Ollama model (e.g. `gpt-oss:20b`) to reason about the best industry match.
- Validates LLM output using Pydantic models.
- Returns SIC and NAICS codes with reasoning.

**Output:** `data-prep/safeguard_matches.csv`

**Prerequisites:**

- Ollama running locally with the chosen model pulled.
- `data-prep/1987_sic_to_1997_naics.xls` (from `naics_sic_xwalk_DL.R`).

**Dependencies:** `ollama`, `pandas`, `scikit-learn`, `pydantic`

---

## 4. `jones.R`

**Purpose:** Compute discretionary accruals (earnings management measures) using the Jones (1991) model on Compustat data.

**What it does:**

- Connects to WRDS using credentials from `secrets.csv`.
- Downloads US firm financial statement data (Compustat).
- Computes total accruals and alternative accrual measures.
- Constructs control variables (ΔRevenue, PPE, ROA, etc.).
- Filters to US, non-financial firms and constructs SIC sector codes.

**Output:** `data-prep/jones_residuals.csv` (firm-year panel with accrual measures).

**Prerequisites:**

- Valid WRDS credentials in `secrets.csv` (`user`, `pass`).
- Working WRDS PostgreSQL connection.
- `load_libraries.R` available.

**Dependencies:** `RPostgres`, `tidyverse`, `duckdb`

---

## 5. `phd-lecture-analyses.R`

**Purpose:** Run the final event-study analysis linking safeguard investigations to firm earnings management.

**What it does:**

- Loads cleaned investigation data with matched NAICS codes.
- Loads firm accrual data from `jones_residuals.csv`.
- Defines treated and control cohorts around investigation dates.
- Builds a panel with ±6-year windows around each investigation.
- Constructs time-to-event variables and analysis-ready datasets.

**Output:** Event-study panel datasets used in lecture materials and paper summaries.

**Dependencies:** `load_libraries.R`, `duckdb`, `safeguard_matches.csv`, `jones_residuals.csv`

---

## 6. `naics_sic_xwalk_DL.R`

**Purpose:** Download and prepare the SIC–NAICS crosswalk used for industry matching.

**What it does:**

- Downloads crosswalk data from Census/official sources.
- Cleans column names and formats SIC/NAICS codes.
- Produces a standardized Excel file used by `industry_match_chat.py`.

**Output:** `data-prep/1987_sic_to_1997_naics.xls`

**Dependencies:** `tidyverse`, `readxl`, `writexl` (or analogous packages)

---

## 7. `load_libraries.R`

**Purpose:** Central place to load and configure R package dependencies.

**What it does:**

- Loads commonly used packages (`tidyverse`, `RPostgres`, `duckdb`, etc.).
- Sets global options (e.g. printing, scientific notation, parallel settings).
- Optionally installs missing packages on first run.

**Used by:** `jones.R`, `phd-lecture-analyses.R`, and other R scripts.

---

## 8. `etable-setup.R`

**Purpose:** Configure regression table formatting for lecture and paper outputs.

**What it does:**

- Sets up `modelsummary` / `etable` or similar table options.
- Defines custom labels, notes, and significance stars.
- Used when generating LaTeX/HTML tables in the analysis scripts.

**Used by:** `phd-lecture-analyses.R` and related R scripts.

---

## 9. `report_to_docling.py` (Auxiliary, Detailed)

**Purpose:** Convert PDF research papers into structured Quarto summaries using a fully local, map–reduce LLM workflow.

### What it does

- Reads PDF files from the `papers/` directory.
- Uses Docling to convert PDFs into high-quality markdown.
- Caches markdown to avoid re-processing unchanged PDFs.
- Splits text into chunks and runs a map–reduce LLM pipeline:
  - **Map step:** Extracts key claims, methods, evidence, and context from each chunk.
  - **Reduce step:** Synthesizes a cohesive academic summary from all chunk outputs.
- Writes a Quarto `.qmd` file with structured sections (research question, methodology, findings, implications).
- Places summaries in `paper_summaries/<paper_name>/`.

**Typical output:**
`paper_summaries/Jones-1991/Jones-1991_summary.qmd`

---

### How to run it

1. **Start Ollama**

   ```bash
   ollama serve
   ```

2. **Run via Poetry (recommended)**

   ```bash
   # Basic usage with map–reduce
   poetry run python data-prep/Scripts/report_to_docling.py papers/my_paper.pdf --map-reduce

   # Specify a particular model
   poetry run python data-prep/Scripts/report_to_docling.py papers/my_paper.pdf --map-reduce --model granite4:latest
   ```

3. **Check the output**

   - Navigate to `paper_summaries/my_paper/`.
   - Open the generated `*_summary.qmd` in your editor or Quarto preview.

---

### Command-line arguments

- `INPUT_PDF` (positional): Path to the PDF file, e.g. `papers/Jones-1991.pdf`.
- `--map-reduce`: Use the multi-step map–reduce pipeline (recommended).
- `--model MODEL_NAME`: Ollama model to use (overrides the default).
- (If present in the script) other flags such as `--no-cache` or `--max-pages` control caching and page limits.

Run:

```bash
poetry run python data-prep/Scripts/report_to_docling.py --help
```

to see the exact argument list supported in your version.

---

### Internal agent workflow

The script uses four conceptual agents:

- **TextSplitterAgent**

  - Splits Docling markdown into paragraph-based chunks.
  - Signature: `run(full_text, chunk_size_target=4000) -> List[str]`.

- **MapAgent**

  - Processes each chunk with `map_prompt.txt`.
  - Extracts:
    - Main claims and arguments
    - Key methodology details
    - Core evidence/results
    - Important context/definitions
  - Signature: `run(text_chunk) -> str`.

- **ReduceAgent**

  - Combines all map outputs using `reduce_prompt.txt`.
  - Produces a structured academic synthesis:
    - Research question
    - Methodology
    - Key findings
    - Implications/conclusions
  - Signature: `run(synthesis_document) -> str`.

- **OrchestratorAgent**
  - Ties everything together: Docling → splitting → map → reduce → Quarto.
  - Signature: `run(full_text) -> str`.

---

### Configuration

**Change default model**

In `report_to_docling.py` (near the top):

```python
OLLAMA_MODEL = "granite4:latest"  # Change to your preferred model
```

Common choices (after `ollama pull <model>`):

- `granite4:latest` (default, balanced)
- `mistral` (smaller, faster)
- `deepseek-r1:8b`
- `llama3`

**Customize extraction**

- Edit `data-prep/Scripts/map_prompt.txt` to change what the map step extracts.
- Current template expects numbered sections like:

  ```
  1. Main Claims: ...
  2. Key Methodology: ...
  3. Core Evidence/Results: ...
  4. Important Context/Definitions: ...
  ```

**Customize synthesis**

- Edit `data-prep/Scripts/reduce_prompt.txt` to adjust the final summary structure.
- Default structure:

  `Research Question → Methodology → Findings → Implications`

**Adjust chunk size**

In `TextSplitterAgent.run()` inside `report_to_docling.py`:

```python
chunks = text_splitter.run(full_text, chunk_size_target=4000)
```

Reduce this for more, smaller chunks; increase it for fewer, larger chunks.

---

### Key files

- `report_to_docling.py` – Main script with integrated map–reduce pipeline.
- `map_prompt.txt` – Prompt template for per-chunk extraction.
- `reduce_prompt.txt` – Prompt template for final synthesis.
- `orchestrator_logic.py` – Optional standalone test harness for the agent pipeline.

---

### Examples

```bash
# Process a single paper
poetry run python data-prep/Scripts/report_to_docling.py papers/Jones-1991.pdf --map-reduce

# Use a faster, smaller model
poetry run python data-prep/Scripts/report_to_docling.py papers/Jones-1991.pdf --map-reduce --model mistral

# Test orchestrator with dummy data (if available)
poetry run python data-prep/Scripts/orchestrator_logic.py
```

---

### Troubleshooting

- **Model not found**

  ```bash
  ollama pull granite4:latest
  ```

- **Connection refused**

  ```bash
  ollama serve
  ```

- **Slow processing**

  - Use a smaller model (e.g. `mistral`).
  - Reduce chunk size (fewer tokens per call).
  - Limit pages processed if your script supports it.

- **Low-quality summaries**
  - Try a larger model.
  - Tailor `map_prompt.txt` and `reduce_prompt.txt` to your field.

---

## Recommended Running Order

**Initial setup:**

1. `load_libraries.R` – Configure the R environment.
2. `naics_sic_xwalk_DL.R` – Download and prepare industry crosswalk.

**Data pipeline (sequential):**

1. `get_data.py` – Scrape USITC investigations.
2. `select_cases.R` – Clean and filter investigations.
3. `industry_match_chat.py` – Match industries with LLM.
4. `jones.R` – Compute earnings management measures.
5. `phd-lecture-analyses.R` – Run final event-study analysis.

**Optional / independent:**

- `report_to_docling.py` – Summarize research papers (standalone).
- `etable-setup.R` – Configure regression table formatting.

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
