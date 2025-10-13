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
-- Step 4: Create flat table for analysis (R/Python/Stata compatible)
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
    
    -- Array counts (complex fields converted to simple counts)
    COALESCE(array_length("Countries"), 0) as countries_count,
    COALESCE(array_length("Participants"), 0) as participants_count,
    COALESCE(array_length("Staff"), 0) as staff_count,
    COALESCE(array_length("Investigation Categories"), 0) as investigation_categories_count,
    COALESCE(array_length("Commerce Orders"), 0) as commerce_orders_count,
    COALESCE(array_length("Hearing Witnesses"), 0) as hearing_witnesses_count,
    COALESCE(array_length("HTS Number"), 0) as hts_numbers_count,
    COALESCE(array_length("Investigation Documents"), 0) as documents_count,
    COALESCE(array_length("Intellectual Property"), 0) as intellectual_property_count,
    COALESCE(array_length("Sub-investigation"), 0) as sub_investigations_count,
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
-- Create indexes for better query performance
-- ============================================================================
CREATE INDEX idx_investigation_id ON ict_investigations_flat(investigation_id);
CREATE INDEX idx_investigation_number ON ict_investigations_flat(investigation_number);
CREATE INDEX idx_start_date ON ict_investigations_flat(start_date);
CREATE INDEX idx_investigation_type ON ict_investigations_flat(investigation_type);

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
