# USITC Investigations Database

## Overview

This database contains investigation data from the United States International Trade Commission (USITC), downloaded from their Investigations Database System (IDS).

**Data Source:** https://ids.usitc.gov/investigations.json  
**Metadata:** https://catalog.data.gov/harvest/object/a435b9f9-d7fa-4c98-b1a5-218eb9789e03  
**Database Location:** `~/Dropbox/Github Data/phd-lecture-dec/DB/ict_data.duckdb`

## Tables

### 1. `ict_raw`

Raw JSON data as imported from the source. Contains `data`, `date`, and `count` fields.

### 2. `ict_metadata`

Dataset metadata including:

- `last_updated`: Timestamp when data was last updated at source
- `total_investigations`: Total number of investigations in dataset
- `imported_at`: Timestamp when data was imported into our database

### 3. `ict_investigations`

Full normalized table with all fields from the JSON, including complex nested structures (STRUCTs and arrays). This table has 90 columns including:

- Investigation IDs and numbers
- Full investigation details
- Nested arrays for Countries, Participants, Staff, etc.
- Complete historical information

**Use this table when you need:** Access to complex nested data structures, complete historical records, detailed participant/staff information.

### 4. `ict_investigations_flat` ⭐ **RECOMMENDED FOR ANALYSIS**

Flattened table designed for statistical analysis in R, Python, and Stata. **This is the table you should use for most analysis tasks.**

**Contains 4,239 investigations spanning 1930-2025**

#### Key Features:

- All scalar fields extracted
- Complex arrays converted to counts (e.g., `countries_count`, `participants_count`)
- Boolean fields properly typed
- Date fields properly formatted
- **47 columns total** - clean and analysis-ready

#### Column Groups:

**Identifiers (4 columns):**

- `investigation_id`, `investigation_number`, `docket_number`, `case_id`

**Investigation Details (6 columns):**

- `full_title`, `topic`, `investigation_type`, `investigation_phase`, `investigation_status`, `investigation_status_id`

**Date Fields (12 columns):**

- `start_date`, `vote_date`, `determination_date`
- `commerce_initiation_date`, `commerce_prelim_ad_date`, `commerce_final_ad_date`
- `commerce_prelim_cvd_date`, `commerce_final_determination_date`
- `hearing_start_date`, `hearing_end_date`, `investigation_end_date`, `initiating_document_received_date`

**Boolean Flags (5 columns):**

- `is_active`, `is_operational`, `is_recurring`, `is_split_final`, `has_internal_remand`

**Array Counts (11 columns):**

- `countries_count` - Number of countries involved
- `participants_count` - Number of participants
- `staff_count` - Number of staff members assigned
- `investigation_categories_count` - AD/CVD categories
- `commerce_orders_count` - Commerce department orders
- `hearing_witnesses_count` - Number of witnesses
- `hts_numbers_count` - Harmonized Tariff Schedule codes
- `documents_count` - Investigation documents
- `intellectual_property_count` - IP items involved
- `sub_investigations_count` - Related sub-investigations
- `mini_schedule_count` - Schedule milestones

**Case Management (8 columns):**

- `category_basket` - Product category
- `case_manager_last_name`, `case_manager_first_name`, `case_manager_email`
- `itc_qs_issued`, `itc_qs_returned` - Questionnaire dates
- `staff_report_due`, `party_comments_due` - Deadline dates

**Metadata (1 column):**

- `imported_at` - Timestamp when record was imported

## Investigation Types

The database contains 6 types of investigations:

1. **Import Injury** (1,837 investigations) - Anti-dumping (AD) and Countervailing duty (CVD) cases
2. **Unfair Imports** (1,603 investigations) - Section 337 cases
3. **Factfinding** (757 investigations) - Industry and economic analysis
4. **Rule Making** (29 investigations)
5. **Tariff Affairs and Trade Agreements** (10 investigations)
6. **Byrd Amendment** (3 investigations)

## Usage Examples

### R

```r
library(duckdb)
library(tidyverse)

# Connect (read-only recommended)
con <- dbConnect(duckdb(),
                 dbdir = "~/Dropbox/Github Data/phd-lecture-dec/DB/ict_data.duckdb",
                 read_only = TRUE)

# Load flat table
investigations <- dbReadTable(con, "ict_investigations_flat")

# Or use dplyr
investigations <- tbl(con, "ict_investigations_flat") %>%
  filter(investigation_type == "Import Injury") %>%
  collect()

# Remember to disconnect
dbDisconnect(con, shutdown = TRUE)
```

### Python

```python
import duckdb
import pandas as pd

# Connect
con = duckdb.connect('~/Dropbox/Github Data/phd-lecture-dec/DB/ict_data.duckdb',
                     read_only=True)

# Query
df = con.execute("""
    SELECT *
    FROM ict_investigations_flat
    WHERE investigation_type = 'Import Injury'
    AND start_date >= '2020-01-01'
""").df()

# Close connection
con.close()
```

### Stata

```stata
* First export from DuckDB to CSV
* Then in Stata:
import delimited "investigations_flat.csv", clear
```

### SQL (DuckDB CLI)

```sql
duckdb ~/Dropbox/Github Data/phd-lecture-dec/DB/ict_data.duckdb

-- Active investigations by type
SELECT investigation_type, COUNT(*) as count
FROM ict_investigations_flat
WHERE is_active = true
GROUP BY investigation_type
ORDER BY count DESC;

-- Recent investigations
SELECT investigation_number, topic, start_date, countries_count
FROM ict_investigations_flat
WHERE start_date >= '2024-01-01'
ORDER BY start_date DESC;
```

## Updating the Data

To refresh the database with latest data:

```bash
cd ~/Github/phd-lecture-dec
./download_ict.bash
```

This will:

1. Download latest JSON from USITC
2. Delete old database
3. Create new database with all 4 tables
4. Display summary statistics

**Runtime:** ~10 seconds (downloads 31.5 MB)

## Database Schema

View full schema:

```bash
duckdb ~/Dropbox/Github Data/phd-lecture-dec/DB/ict_data.duckdb -c "DESCRIBE ict_investigations_flat;"
```

## Notes

- **Recommended:** Use `ict_investigations_flat` for statistical analysis
- **Advanced:** Use `ict_investigations` when you need to access nested structures
- All dates are properly typed as DATE
- Boolean fields are true/false (not 0/1)
- Array counts are 0 if field is NULL or empty
- Database uses DuckDB format (not SQLite) - requires duckdb library

## Support

For questions about the data structure, see:

- USITC IDS: https://ids.usitc.gov/
- Data.gov metadata: https://catalog.data.gov/harvest/object/a435b9f9-d7fa-4c98-b1a5-218eb9789e03

For questions about this database implementation, check the script: `download_ict.bash`
