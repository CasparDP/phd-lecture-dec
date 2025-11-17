#!/usr/bin/env python3
"""
Match safeguard investigation titles to the closest SIC/NAICS codes
using your 1987 SIC–NAICS crosswalk and GPT reasoning.
"""
import os
import duckdb
import pandas as pd
import ollama
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from typing import Optional

# ---------------------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------------------

# Path to your Excel file with columns:
# ["SIC", "Part Indicator", "SIC Titles and Part Descriptions", "1997 NAICS", "1997 NAICS Titles and Part Indicators"]
CROSSWALK_PATH = 'data-prep/1987_sic_to_1997_naics.xls'

# Safeguard case titles with investigation IDs for later joining
CASES_DF = pd.read_csv('data-prep/llm_usitc_safeguards_input.csv')[['clean_title', 'investigation_id']]

# Top N candidate rows to send to Ollama for each case
TOP_N = 10

# Whether to include raw LLM response in output (set to False for production)
INCLUDE_RAW = False

# Model to use (e.g., "mistral", "neural-chat", "llama2", etc.)
# Make sure the model is pulled in Ollama first
MODEL = "gpt-oss:20b"

# Note: Ollama runs locally, so no API key is needed
# Make sure Ollama is running before executing this script

# ---------------------------------------------------------------------
# 2. PYDANTIC MODELS FOR TYPE CHECKING
# ---------------------------------------------------------------------

class IndustryMatch(BaseModel):
    """Validated model for industry matching results."""
    model_config = ConfigDict(populate_by_name=True)

    case_title: str
    best_match_SIC: str = Field(..., description="SIC code")
    best_match_NAICS: str = Field(..., description="NAICS code")
    reasoning: str = Field(..., description="One sentence explaining the match")


class MatchResult(BaseModel):
    """Result wrapper that allows partial matches or errors."""
    case_title: str
    investigation_id: Optional[str] = None
    best_match_SIC: Optional[str] = None
    best_match_NAICS: Optional[str] = None
    reasoning: Optional[str] = None
    error: Optional[str] = None
    raw: Optional[str] = None

# ---------------------------------------------------------------------
# 3. LOAD AND PREPARE CROSSWALK
# ---------------------------------------------------------------------

crosswalk = pd.read_excel(CROSSWALK_PATH)

# Standardize column names (handle potential spaces/variations)
crosswalk.columns = crosswalk.columns.str.strip()

# Create a full SIC identifier combining SIC and Part Indicator
crosswalk["SIC_Full"] = crosswalk["SIC"].astype(str) + (
    " " + crosswalk["Part Indicator"].fillna("").astype(str)
).str.rstrip()

# Remove rows with missing descriptions or NAICS codes
crosswalk = crosswalk.dropna(subset=[
    "SIC Titles and Part Descriptions",
    "1997 NAICS Titles and Part Indicators"
])

# Ensure all text columns are strings
crosswalk["SIC Titles and Part Descriptions"] = crosswalk["SIC Titles and Part Descriptions"].astype(str)
crosswalk["1997 NAICS Titles and Part Indicators"] = crosswalk["1997 NAICS Titles and Part Indicators"].astype(str)
crosswalk["1997 NAICS"] = crosswalk["1997 NAICS"].astype(str)

# Save a copy of the cleaned crosswalk for reference
crosswalk.to_csv("data-prep/cleaned_sic_naics_crosswalk.csv", index=False)

# ---------------------------------------------------------------------
# 4. TEXT-SIMILARITY HELPER
# ---------------------------------------------------------------------

def get_top_candidates(title: str, df: pd.DataFrame, top_n: Optional[int] = None):
    """Return the top_n crosswalk rows most textually similar to the title."""
    if top_n is None:
        top_n = TOP_N
    corpus = df["SIC Titles and Part Descriptions"].tolist() + [title]
    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(corpus)
    sims = cosine_similarity(X[-1], X[:-1]).flatten()
    top_idx = sims.argsort()[-top_n:][::-1]
    return df.iloc[top_idx].copy()

# ---------------------------------------------------------------------
# 5. MAIN LOOP
# ---------------------------------------------------------------------

results = []

for _, row in CASES_DF.iterrows():
    title = row['clean_title']
    investigation_id = row['investigation_id']

    candidates = get_top_candidates(title, crosswalk, TOP_N)
    candidate_rows = "\n".join(
        f"SIC: {row.SIC_Full} | SIC Description: {row['SIC Titles and Part Descriptions']} | "
        f"NAICS: {row['1997 NAICS']} | NAICS Description: {row['1997 NAICS Titles and Part Indicators']}"
        for _, row in candidates.iterrows()
    )

    prompt = f"""You are an industry classifier. Match the case title to the best industry.

CASE TITLE: "{title}"

CANDIDATE INDUSTRIES:
{candidate_rows}

INSTRUCTIONS:
1. Find the best matching industry for the case title
2. Look for keywords that match industry descriptions
3. Return ONLY a JSON response with no other text

JSON FORMAT (example):
{{"case_title": "Footwear", "best_match_SIC": "3140", "best_match_NAICS": "31640", "reasoning": "Direct match to footwear manufacturing."}}

Fields to include:
- case_title: The original case title
- best_match_SIC: The SIC code (e.g., "0111")
- best_match_NAICS: The NAICS code (e.g., "11114")
- reasoning: One sentence explaining the match

Return JSON ONLY:"""

    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=False
    )

    content = response["message"]["content"].strip()

    # Parse and validate JSON with Pydantic
    try:
        parsed_dict = json.loads(content)
        # Attempt strict validation
        validated = IndustryMatch(**parsed_dict)
        result = MatchResult(**validated.model_dump(), investigation_id=investigation_id, raw=content if INCLUDE_RAW else None)
    except json.JSONDecodeError:
        result = MatchResult(case_title=title, investigation_id=investigation_id, error="JSON parse failed", raw=content if INCLUDE_RAW else None)
    except ValidationError as ve:
        # Partial validation failed - store the raw data but mark the error
        try:
            parsed_dict = json.loads(content)
            result = MatchResult(case_title=title, investigation_id=investigation_id, error=f"Validation error: {ve}", raw=content if INCLUDE_RAW else None, **parsed_dict)
        except:
            result = MatchResult(case_title=title, investigation_id=investigation_id, error="JSON parse and validation failed", raw=content if INCLUDE_RAW else None)

    results.append(result.model_dump())
    print(result.model_dump())

# ---------------------------------------------------------------------
# 6. SAVE RESULTS
# ---------------------------------------------------------------------

pd.DataFrame(results).to_csv("data-prep/safeguard_matches.csv", index=False)


# Save to DuckDB for further analysis
duckdb_path = os.path.join("data-prep/DB/jones_duckdb")
con = duckdb.connect(duckdb_path)
results_df = pd.DataFrame(results)
con.execute("CREATE TABLE IF NOT EXISTS safeguard_matches AS SELECT * FROM results_df;")
con.close()

print("\n✅ Matching complete — results saved to safeguard_matches.csv and DuckDB")
