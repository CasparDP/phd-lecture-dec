import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import time
from urllib.parse import urljoin
from collections import defaultdict

# -----------------------------
# 1. Parameters
# -----------------------------
BASE_URL = "https://www.usitc.gov/commission_publications_library"

# Output directory (portable path using $HOME)
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Dropbox", "Github Data", "phd-lecture-dec", "commission_publications_lib")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Raw HTML cache directory
HTML_CACHE_DIR = os.path.join(OUTPUT_DIR, "raw_html_cache")
os.makedirs(HTML_CACHE_DIR, exist_ok=True)

# Request headers (Cloudflare requires proper browser headers)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# Query parameters (no filters - get all publications)
PARAMS = {
    "order": "field_pub_arch_pub_date_1",
    "sort": "asc"
}

# Source: https://www.census.gov/naics/concordances/1987_SIC_to_1997_NAICS.xls
CROSSWALK_URL = "https://www.census.gov/naics/concordances/1987_SIC_to_1997_NAICS.xls"
CROSSWALK_FILE = os.path.join(os.path.expanduser("~"), "Dropbox", "Github Data", "phd-lecture-dec", "1987_SIC_to_1997_NAICS.xls")

# Download crosswalk file if it doesn't exist
def ensure_crosswalk_file():
    """Download NAICS crosswalk file if not already present."""
    if os.path.exists(CROSSWALK_FILE):
        print(f"Using existing crosswalk file: {CROSSWALK_FILE}")
        return
    
    print(f"Downloading crosswalk file from {CROSSWALK_URL}")
    os.makedirs(os.path.dirname(CROSSWALK_FILE), exist_ok=True)
    
    try:
        r = requests.get(CROSSWALK_URL, timeout=30)
        r.raise_for_status()
        with open(CROSSWALK_FILE, 'wb') as f:
            f.write(r.content)
        print(f"Successfully downloaded to {CROSSWALK_FILE}")
    except Exception as e:
        print(f"Error downloading crosswalk file: {e}")
        raise

# Large industry definitions: 2-digit NAICS with significant US employment
# These sectors employ >200k workers or have major economic significance
LARGE_INDUSTRIES = {
    "31": ("Manufacturing", True),  # ~12.7M employees
    "42": ("Wholesale Trade", True),  # ~6M employees
    "44": ("Retail Trade", True),  # ~15.8M employees
    "51": ("Information", True),  # ~2.9M employees
    "52": ("Finance & Insurance", True),  # ~6.1M employees
    "54": ("Professional Services", True),  # ~8.4M employees
    "72": ("Accommodation & Food", True),  # ~11.4M employees
}

STOPWORDS = {
    "products", "goods", "services", "materials", "articles", "items",
    "certain", "other", "related", "various", "and", "the", "a", "or",
    "not", "from", "for", "with", "as", "such", "including", "whether",
    "apparatus", "equipment", "machinery", "device", "system", "tool",
    "supplement", "manufacturing", "production", "use", "used", "based",
    "made", "manufactured", "component", "components", "part", "parts",
    "of", "in", "on", "by", "at", "to"
}

# -----------------------------
# 2. Build NAICS keyword dictionary with improvements
# -----------------------------
def build_crosswalk(path):
    """
    Load SIC→NAICS file and build keyword dictionary with:
    - Filtered stopwords
    - 2-digit sector classification
    - Multi-word phrase support
    """
    # Read the Excel file with proper header
    df = pd.read_excel(path, header=0)
    
    # Convert column names to lowercase strings
    df.columns = [str(c).lower() for c in df.columns]

    # Identify the relevant columns (NAICS code and title)
    naics_code_col = "1997 naics"  # Column with NAICS codes
    naics_title_col = "1997 naics titles and part indicators"  # Column with NAICS titles

    # Build multi-level mapping: word → list of (code, title, sector, is_large)
    crosswalk = defaultdict(list)
    
    for _, row in df.iterrows():
        # Get code and title, converting to string
        code_val = row[naics_code_col]
        title_val = row[naics_title_col]
        
        # Skip if either is NaN or None
        if pd.isna(code_val) or pd.isna(title_val):
            continue
        
        code = str(int(code_val)).strip() if isinstance(code_val, (int, float)) else str(code_val).strip()
        title = str(title_val).strip().lower()
        
        if not code or not title:
            continue
        
        # Extract 2-digit sector code
        sector = code[:2] if len(code) >= 2 else None
        is_large = sector in LARGE_INDUSTRIES if sector else False
        sector_name = LARGE_INDUSTRIES.get(sector, (None, False))[0] if sector else None
        
        # Index all significant keywords
        words = re.findall(r"[a-z]+", title)
        for word in words:
            if len(word) > 3 and word not in STOPWORDS:
                # Store list to preserve all matches
                crosswalk[word].append({
                    "code": code,
                    "title": title,
                    "sector": sector,
                    "sector_name": sector_name,
                    "is_large": is_large
                })
    
    # Remove duplicates, keep only unique NAICS per word
    for word in crosswalk:
        unique_codes = {}
        for item in crosswalk[word]:
            if item["code"] not in unique_codes:
                unique_codes[item["code"]] = item
        crosswalk[word] = list(unique_codes.values())
    
    return dict(crosswalk)

# Ensure crosswalk file is available (download if needed)
ensure_crosswalk_file()

NAICS_CROSSWALK = build_crosswalk(CROSSWALK_FILE)

# -----------------------------
# 3. Scraping helpers
# -----------------------------
def get_total_pages():
    """Find total number of pages in publications with retry logic and delay."""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Add delay before request to avoid rate limiting
            if attempt > 0:
                delay = 3 * (2 ** (attempt - 1))  # 3s, 6s, 12s, 24s
                print(f"Waiting {delay}s before retry...")
                time.sleep(delay)
            
            r = requests.get(BASE_URL, params=PARAMS, headers=HEADERS, timeout=15)
            r.raise_for_status()
            
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Check for Cloudflare challenge
            if "Challenge Validation" in r.text:
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1}/{max_retries}: Got Cloudflare challenge, retrying...")
                    continue
                else:
                    print("Failed to bypass Cloudflare protection after retries.")
                    return 0
            
            # Method 1: Look for "Displaying X - Y of TOTAL" text
            text = soup.get_text()
            import re as regex_module
            match = regex_module.search(r"Displaying\s+\d+\s*-\s*(\d+)\s+of\s+(\d+)", text)
            if match:
                items_per_page = int(match.group(1))
                total_items = int(match.group(2))
                total_pages = (total_items + items_per_page - 1) // items_per_page  # Ceiling division
                print(f"Found total items: {total_items}, items per page: {items_per_page}")
                return total_pages - 1  # Pages are 0-indexed
            
            # Method 2: Look for pagination page numbers (USA Design System style)
            pagers = soup.select(".usa-pagination__item.usa-pagination__page-no")
            if pagers:
                # Get all page numbers
                page_nums = []
                for p in pagers:
                    try:
                        num = int(p.get_text(strip=True))
                        page_nums.append(num)
                    except ValueError:
                        pass
                
                if page_nums:
                    # If we have page numbers like [1,2,3,4,5,6,7,8,9] but see "..." before "Last",
                    # we need to actually click "Last" or use a smarter approach
                    # For now, return the max we found
                    return max(page_nums) - 1
            
            return 0
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"Attempt {attempt + 1}/{max_retries}: Got 403 Forbidden, retrying with delay...")
                time.sleep(5)
            else:
                raise
        except Exception as e:
            print(f"Error getting total pages (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return 0
            time.sleep(2)
    
    print("Failed to fetch pages after retries.")
    return 0

def get_cached_page_path(page_num):
    """Get the file path for a cached page."""
    return os.path.join(HTML_CACHE_DIR, f"page_{page_num:04d}.html")

def save_page_html(page_num, html_content):
    """Save raw HTML to cache directory."""
    cache_path = get_cached_page_path(page_num)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    except Exception as e:
        print(f"Warning: Could not save page {page_num} to cache: {e}")

def load_page_html(page_num):
    """Load raw HTML from cache if it exists."""
    cache_path = get_cached_page_path(page_num)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not load cached page {page_num}: {e}")
    return None

def fetch_page(page_num):
    """Fetch a page with retry logic, delays, and Cloudflare challenge handling.
    
    First checks cache, then fetches if needed and saves to cache.
    """
    # Check cache first
    cached_html = load_page_html(page_num)
    if cached_html:
        print(f"    (from cache)", end=" ")
        return cached_html
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            params = PARAMS.copy()
            params["page"] = page_num
            
            # Add respectful delay to avoid rate limiting
            if attempt == 0:
                time.sleep(1)  # Always wait before first request
            else:
                delay = 3 * (2 ** (attempt - 1))  # 3s, 6s, 12s, 24s
                print(f"    Retry delay: {delay}s")
                time.sleep(delay)
            
            r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
            r.raise_for_status()
            
            # Check for Cloudflare challenge
            if "Challenge Validation" in r.text:
                if attempt < max_retries - 1:
                    print(f"    Attempt {attempt + 1}/{max_retries}: Got Cloudflare challenge, retrying...")
                    continue
                else:
                    print(f"    Failed to fetch page {page_num} after {max_retries} attempts")
                    return ""
            
            # Save to cache before returning
            save_page_html(page_num, r.text)
            return r.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"    Attempt {attempt + 1}/{max_retries}: Got 403, retrying...")
                time.sleep(5)
            else:
                raise
        except Exception as e:
            print(f"    Error fetching page {page_num} (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return ""
            time.sleep(2)
    
    return ""

def parse_titles(html):
    """Extract all publication data from HTML table.
    
    Returns list of dicts with keys: pub_number, title, date, subject, type, link, pub_file_link
    """
    soup = BeautifulSoup(html, "html.parser")
    publications = []
    
    # New structure: table rows with publication data
    # Columns: [0] Pub #, [1] Title, [2] Date, [3] Subject, [4] Type
    rows = soup.select("table tbody tr")
    for row in rows:
        cells = row.select("td")
        if len(cells) >= 5:
            # Extract pub number and its href (from the first column)
            pub_num_cell = cells[0]
            pub_number = pub_num_cell.get_text(strip=True)
            
            # Try to find a link in the pub number cell
            pub_num_link_el = pub_num_cell.select_one("a")
            if pub_num_link_el and pub_num_link_el.get("href"):
                pub_file_link = pub_num_link_el["href"]
            else:
                pub_file_link = ""
            
            title_cell = cells[1]
            title_text = title_cell.get_text(separator=" ", strip=True)
            date_text = cells[2].get_text(strip=True)
            subject_text = cells[3].get_text(strip=True)
            type_text = cells[4].get_text(strip=True)
            
            # Skip "Number Not Used" entries
            if "Number Not Used" in title_text:
                continue
            
            # Try to find a link in the title cell
            link_el = title_cell.select_one("a")
            if link_el:
                link = urljoin(BASE_URL, link_el["href"])
            else:
                link = ""
            
            if title_text and title_text != "Number Not Used":
                publications.append({
                    "pub_number": pub_number,
                    "title": title_text,
                    "date": date_text,
                    "subject": subject_text,
                    "type": type_text,
                    "link": link,
                    "pub_file_link": pub_file_link
                })
    
    return publications

def clean_title(title):
    t = title.lower()
    t = re.sub(r"^certain\s+", "", t)
    t = re.sub(r"\s+from.*$", "", t)
    t = re.sub(r"[^a-z0-9\s]", "", t)
    return t.strip()

def match_naics(title):
    """
    Match title to NAICS with smart scoring:
    - Prioritize matches from LARGE_INDUSTRIES
    - Return all matches with confidence
    - Score by keyword specificity
    - Returns diagnostic info about why match succeeded/failed
    """
    tokens = set(re.findall(r"[a-z]+", title))
    matched_keywords = []
    unmatched_keywords = []
    
    # Collect all potential matches with scoring
    matches = defaultdict(lambda: {"score": 0, "keyword_count": 0, "is_large": False})
    
    for word in tokens:
        if word in NAICS_CROSSWALK:
            matched_keywords.append(word)
            for item in NAICS_CROSSWALK[word]:
                code = item["code"]
                matches[code]["score"] += 1  # Each keyword match adds 1 point
                matches[code]["keyword_count"] += 1
                matches[code]["title"] = item["title"]
                matches[code]["sector"] = item["sector"]
                matches[code]["sector_name"] = item["sector_name"]
                matches[code]["is_large"] = item["is_large"]  # Capture large industry flag
        else:
            unmatched_keywords.append(word)
    
    if not matches:
        return {
            "naics": None,
            "industry": None,
            "sector": None,
            "sector_name": None,
            "match_confidence": 0.0,
            "is_large_industry": False,
            "all_matches": [],
            "matched_keywords": "",
            "unmatched_keywords": ",".join(sorted(unmatched_keywords)[:10]),  # Top 10 unmatched
            "total_tokens": len(tokens)
        }
    
    # Sort by: (1) is_large, (2) match score, (3) code specificity
    sorted_matches = sorted(
        matches.items(),
        key=lambda x: (-x[1]["is_large"], -x[1]["score"], -len(x[0])),
        reverse=True
    )
    
    best_code, best_data = sorted_matches[0]
    confidence = min(best_data["keyword_count"] / len(tokens) if tokens else 0, 1.0)
    
    # Return best match with all alternatives
    return {
        "naics": best_code,
        "industry": best_data["title"],
        "sector": best_data["sector"],
        "sector_name": best_data["sector_name"],
        "match_confidence": confidence,
        "is_large_industry": best_data["is_large"],
        "all_matches": [{"naics": k, "title": v["title"], "is_large": v["is_large"]} 
                       for k, v in sorted_matches[:3]],  # Top 3 matches
        "matched_keywords": ",".join(sorted(matched_keywords)),
        "unmatched_keywords": ",".join(sorted(unmatched_keywords)[:10]),  # Top 10 unmatched
        "total_tokens": len(tokens)
    }

# =============================
# 5. Scrape all pages automatically
# =============================
import sys

# Optional: limit pages for testing (set to None for all pages)
# Usage: python get_data.py 10  (to scrape first 10 pages)
MAX_PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else None

total_pages = get_total_pages()
print(f"Detected {total_pages} pages in Import Injury publications.")

if MAX_PAGES:
    print(f"⚠️  LIMITED TO FIRST {MAX_PAGES} PAGES FOR TESTING")
    total_pages = min(MAX_PAGES, total_pages)

records = []
for page in range(total_pages + 1):
    print(f"Scraping page {page}/{total_pages} ...", end=" ", flush=True)
    html = fetch_page(page)
    page_records = 0
    for pub_data in parse_titles(html):
        # Extract from table columns
        title = pub_data["title"]
        cleaned = clean_title(title)
        match_result = match_naics(cleaned)
        
        records.append({
            "pub_number": pub_data["pub_number"],
            "title": title,
            "date": pub_data["date"],
            "subject": pub_data["subject"],
            "type": pub_data["type"],
            "cleaned_title": cleaned,
            "naics": match_result["naics"],
            "industry": match_result["industry"],
            "sector": match_result["sector"],
            "sector_name": match_result["sector_name"],
            "match_confidence": match_result["match_confidence"],
            "is_large_industry": match_result["is_large_industry"],
            "alternative_matches": str(match_result["all_matches"]),
            "matched_keywords": match_result.get("matched_keywords", ""),
            "unmatched_keywords": match_result.get("unmatched_keywords", ""),
            "total_keywords": match_result.get("total_tokens", 0),
            "link": pub_data["link"],
            "pub_file_link": pub_data.get("pub_file_link", "")
        })
        page_records += 1
    print(f"({page_records} records)")

df = pd.DataFrame(records)
print(f"\n{'='*80}")
print(f"Scraped {len(df)} publications total.")
print(f"{'='*80}")

if len(df) == 0:
    print("Warning: No publications were scraped. The DataFrame is empty.")
    print("This may be due to website changes or connectivity issues.")
else:
    print(f"Large industry matches: {df['is_large_industry'].sum()} ({100*df['is_large_industry'].sum()/len(df):.1f}%)")
    print(f"Average match confidence: {df['match_confidence'].mean():.2f}")
    print(f"\nTop industries by frequency:")
    print(df['industry'].value_counts().head(10))

# Save to portable path
full_csv = os.path.join(OUTPUT_DIR, "usitc_import_injury_crosswalk_full.csv")
df.to_csv(full_csv, index=False)
print(f"\nSaved to {full_csv}")

# Also save filtered version for large industries only
if len(df) > 0:
    df_large = df[df['is_large_industry']].copy()
    large_csv = os.path.join(OUTPUT_DIR, "usitc_import_injury_crosswalk_large_industries.csv")
    df_large.to_csv(large_csv, index=False)
    print(f"Saved {len(df_large)} large industry cases to {large_csv}")
else:
    print("No data to save for large industries.")
