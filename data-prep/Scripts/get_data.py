import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import time
from urllib.parse import urljoin
import sys
import duckdb

# =============================
# 1. Parameters
# =============================
BASE_URL = "https://www.usitc.gov/commission_publications_library"

# Output directory - save to parent data-prep folder
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..")
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

# =============================
# 2. Scraping Helpers
# =============================
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

    # Table rows with publication data
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


# =============================
# 3. Scrape all pages automatically
# =============================
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
        records.append({
            "pub_number": pub_data["pub_number"],
            "title": pub_data["title"],
            "date": pub_data["date"],
            "subject": pub_data["subject"],
            "type": pub_data["type"],
            "link": pub_data["link"],
            "pub_file_link": pub_data["pub_file_link"]
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
    print(f"\nTop subjects by frequency:")
    print(df['subject'].value_counts().head(10))

# Save to data-prep directory
output_csv = os.path.join(OUTPUT_DIR, "usitc_import_injury.csv")
df.to_csv(output_csv, index=False)
print(f"\nSaved to {output_csv}")

# Save to DuckDB
duckdb_path = os.path.join(OUTPUT_DIR, "DB/jones_duckdb")
con = duckdb.connect(duckdb_path)
con.register("df", df)
con.execute("DROP TABLE IF EXISTS usitc_import_injury;")
con.execute("CREATE TABLE usitc_import_injury AS SELECT * FROM df;")
con.close()
print(f"Saved to DuckDB database at {duckdb_path}")

print("\n✅ Run summary:")
try:
    total_scraped = len(df)
except Exception:
    total_scraped = 0

print(f"  ✅ Total publications scraped: {total_scraped}")
print(f"  ✅ CSV file saved: {output_csv}")
print(f"  ✅ DuckDB database file/location: {duckdb_path}")
print(f"  ✅ Raw HTML cache directory: {HTML_CACHE_DIR}")
print(f"  ✅ Output directory: {OUTPUT_DIR}")

if total_scraped > 0:
    print("\n✅ Top subjects by frequency (top 10):")
    try:
        top_subs = df['subject'].value_counts().head(10)
        print(top_subs.to_string())
    except Exception as e:
        print(f"  ⚠️ Could not display subject frequencies: {e}")

print("\n✅ All done. If you experienced issues (empty results or Cloudflare challenges),")
print("   try rerunning with a smaller page limit, longer delays, or inspect the raw HTML cache for errors.")
