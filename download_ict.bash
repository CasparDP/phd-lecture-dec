#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# USITC Investigations Database Download Script (v3)
# ============================================================================
# This script downloads USITC investigation data and creates a flat,
# analysis-ready table in DuckDB compatible with R, Python, and Stata.
#
# Data source: https://ids.usitc.gov/investigations.json
# Metadata: https://catalog.data.gov/harvest/object/a435b9f9-d7fa-4c98-b1a5-218eb9789e03
# ============================================================================

# Configuration
DB_DIR="$HOME/Dropbox/Github Data/phd-lecture-dec/DB"
DB_FILE="$DB_DIR/ict_data.duckdb"
JSON_URL="https://ids.usitc.gov/investigations.json"
JSON_FILE="$DB_DIR/investigations.json"

# Create directory if it doesn't exist
mkdir -p "$DB_DIR"

# Download JSON data
echo "Downloading USITC investigations data..."
curl -L -o "$JSON_FILE" "$JSON_URL"
echo "Download complete. File size: $(du -h "$JSON_FILE" | cut -f1)"

# Remove existing database to start fresh
if [ -f "$DB_FILE" ]; then
    echo "Removing existing database..."
    rm "$DB_FILE"
fi

echo "Creating new database and tables..."

# Create DuckDB database with flattened investigations table
duckdb "$DB_FILE" << EOF
-- ============================================================================
-- Step 1: Create raw data table from JSON
-- ============================================================================
CREATE TABLE ict_raw AS
SELECT * FROM read_json_auto('$JSON_FILE',
    format='auto',
    maximum_object_size=134217728
);

-- ============================================================================
-- Step 2: Extract metadata
-- ============================================================================
CREATE TABLE ict_metadata AS
SELECT 
    date as last_updated,
    count as total_investigations,
    current_timestamp as imported_at
FROM ict_raw;

-- ============================================================================
-- Step 3: Create normalized investigations table with complex structures
-- ============================================================================
CREATE TABLE ict_investigations AS
WITH raw_data AS (
    SELECT unnest(data) as investigation
    FROM ict_raw
)
SELECT investigation.* FROM raw_data;

-- ============================================================================
-- Step 4: Create flat table for analysis with full complex field values
-- (R/Python/Stata compatible - arrays can be unnested in R)
-- ============================================================================
DROP TABLE IF EXISTS ict_investigations_flat;

CREATE TABLE ict_investigations_flat AS
SELECT
    -- Primary identifiers
    "Investigation ID" as investigation_id,
    "Investigation Number" as investigation_number,
    "Docket Number" as docket_number,
    "Case ID" as case_id,
    
    -- Investigation details
    "Full Title" as full_title,
    "Topic" as topic,
    "Investigation Type"."Name" as investigation_type,
    "Investigation Phase"."Name" as investigation_phase,
    "Investigation Status"."Name" as investigation_status,
    "Investigation Status".ID as investigation_status_id,
    
    -- Key dates
    "Start Date" as start_date,
    "Vote Date" as vote_date,
    "Determination Date" as determination_date,
    "Commerce Initiation Date" as commerce_initiation_date,
    "Commerce Preliminary AD Determination Date" as commerce_prelim_ad_date,
    "Commerce Final AD Determination Date" as commerce_final_ad_date,
    "Commerce Preliminary CVD Determination Date" as commerce_prelim_cvd_date,
    "Commerce Final Determination Date" as commerce_final_determination_date,
    "Hearing/Conf Start Date" as hearing_start_date,
    "Hearing/Conf End Date" as hearing_end_date,
    "Investigation End Date" as investigation_end_date,
    "Initiating Document Received Date" as initiating_document_received_date,
    
    -- Boolean fields
    "Is Active?" as is_active,
    "Is Operational?" as is_operational,
    "Is Recurring?" as is_recurring,
    "Is Split Final?" as is_split_final,
    "Has Internal Remand?" as has_internal_remand,
    
    -- IMPROVED: Complex fields WITH VALUES (not just counts)
    -- These can be unnested in R with tidyr::unnest() or used as-is for analysis
    "Countries" as countries,
    COALESCE(array_length("Countries"), 0) as countries_count,
    
    -- Investigation Categories - preserve as array
    "Investigation Categories" as investigation_categories,
    COALESCE(array_length("Investigation Categories"), 0) as investigation_categories_count,
    
    -- Participants array - contains full participant information
    "Participants" as participants,
    COALESCE(array_length("Participants"), 0) as participants_count,
    
    -- Staff array
    "Staff" as staff,
    COALESCE(array_length("Staff"), 0) as staff_count,
    
    -- HTS Numbers array
    "HTS Number" as hts_numbers,
    COALESCE(array_length("HTS Number"), 0) as hts_numbers_count,
    
    -- Additional arrays
    "Hearing Witnesses" as hearing_witnesses,
    COALESCE(array_length("Hearing Witnesses"), 0) as hearing_witnesses_count,
    
    "Commerce Orders" as commerce_orders,
    COALESCE(array_length("Commerce Orders"), 0) as commerce_orders_count,
    
    "Investigation Documents" as investigation_documents,
    COALESCE(array_length("Investigation Documents"), 0) as documents_count,
    
    "Intellectual Property" as intellectual_property,
    COALESCE(array_length("Intellectual Property"), 0) as intellectual_property_count,
    
    "Sub-investigation" as sub_investigations,
    COALESCE(array_length("Sub-investigation"), 0) as sub_investigations_count,
    
    "Mini Schedule" as mini_schedule,
    COALESCE(array_length("Mini Schedule"), 0) as mini_schedule_count,
    
    -- Additional fields
    "Category Basket"."Name" as category_basket,
    "Case Manager"."Staff Last Name" as case_manager_last_name,
    "Case Manager"."Staff First Name" as case_manager_first_name,
    "Case Manager".Email as case_manager_email,
    
    -- Schedule dates
    "ITC Qs Issued" as itc_qs_issued,
    "ITC Qs Returned" as itc_qs_returned,
    "Staff Report Due to Commission" as staff_report_due,
    "Party Comments Due Date" as party_comments_due,
    
    -- Metadata
    current_timestamp as imported_at
FROM ict_investigations;

-- ============================================================================
-- Step 5: Create denormalized tables for easy unnesting in R
-- These tables repeat investigation records to match complex field values
-- ============================================================================

-- Countries expanded table (one row per investigation-country combination)
DROP TABLE IF EXISTS ict_investigations_by_country;
CREATE TABLE ict_investigations_by_country AS
SELECT
    investigation_id,
    investigation_number,
    full_title,
    topic,
    investigation_type,
    start_date,
    country,
    current_timestamp as imported_at
FROM (
    SELECT
        f.investigation_id,
        f.investigation_number,
        f.full_title,
        f.topic,
        f.investigation_type,
        f.start_date,
        country
    FROM ict_investigations_flat f
    LEFT JOIN LATERAL UNNEST(f.countries) AS t(country) ON TRUE
)
WHERE country IS NOT NULL;

-- Investigation Categories expanded table
DROP TABLE IF EXISTS ict_investigations_by_category;
CREATE TABLE ict_investigations_by_category AS
SELECT
    investigation_id,
    investigation_number,
    full_title,
    investigation_type,
    start_date,
    category,
    current_timestamp as imported_at
FROM (
    SELECT
        f.investigation_id,
        f.investigation_number,
        f.full_title,
        f.investigation_type,
        f.start_date,
        category
    FROM ict_investigations_flat f
    LEFT JOIN LATERAL UNNEST(f.investigation_categories) AS t(category) ON TRUE
)
WHERE category IS NOT NULL;

-- HTS Numbers expanded table
DROP TABLE IF EXISTS ict_investigations_by_hts;
CREATE TABLE ict_investigations_by_hts AS
SELECT
    investigation_id,
    investigation_number,
    full_title,
    start_date,
    hts_number,
    current_timestamp as imported_at
FROM (
    SELECT
        f.investigation_id,
        f.investigation_number,
        f.full_title,
        f.start_date,
        hts_number
    FROM ict_investigations_flat f
    LEFT JOIN LATERAL UNNEST(f.hts_numbers) AS t(hts_number) ON TRUE
)
WHERE hts_number IS NOT NULL;

-- ============================================================================
-- Create indexes for better query performance
-- (Note: Cannot index array/struct fields directly in DuckDB)
-- ============================================================================
CREATE INDEX idx_investigation_id ON ict_investigations_flat(investigation_id);
CREATE INDEX idx_investigation_number ON ict_investigations_flat(investigation_number);
CREATE INDEX idx_start_date ON ict_investigations_flat(start_date);
CREATE INDEX idx_investigation_type ON ict_investigations_flat(investigation_type);

CREATE INDEX idx_country_investigation ON ict_investigations_by_country(investigation_id);
CREATE INDEX idx_country_name ON ict_investigations_by_country(country);

CREATE INDEX idx_category_investigation ON ict_investigations_by_category(investigation_id);
CREATE INDEX idx_category_name ON ict_investigations_by_category(category);

CREATE INDEX idx_hts_investigation ON ict_investigations_by_hts(investigation_id);
CREATE INDEX idx_hts_number ON ict_investigations_by_hts(hts_number);

-- ============================================================================
-- Summary Statistics
-- ============================================================================
SELECT 
    'Total investigations' as metric,
    COUNT(*) as value
FROM ict_investigations_flat
UNION ALL
SELECT 
    'Date range',
    MIN(start_date)::VARCHAR || ' to ' || MAX(start_date)::VARCHAR
FROM ict_investigations_flat
WHERE start_date IS NOT NULL
UNION ALL
SELECT 
    'Investigation types',
    COUNT(DISTINCT investigation_type)::VARCHAR
FROM ict_investigations_flat
UNION ALL
SELECT
    'Active investigations',
    SUM(CASE WHEN is_active THEN 1 ELSE 0 END)::VARCHAR
FROM ict_investigations_flat;

EOF

echo ""
echo "============================================================================"
echo "Database created successfully!"
echo "============================================================================"
echo "Location: $DB_FILE"
echo ""
echo "Tables created:"
duckdb "$DB_FILE" -c "SHOW TABLES;"
echo ""
echo "Flat table schema (first 20 columns):"
duckdb "$DB_FILE" -c "DESCRIBE ict_investigations_flat;" | head -20
echo ""
echo "Sample data (first 3 investigations):"
duckdb "$DB_FILE" -c "
SELECT 
    investigation_id,
    investigation_number,
    topic,
    investigation_type,
    start_date,
    countries_count,
    participants_count
FROM ict_investigations_flat 
LIMIT 3;"
echo ""
echo "============================================================================"
echo "Ready for analysis in R, Python, or Stata!"
echo "============================================================================"
