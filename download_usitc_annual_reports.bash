#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# USITC Annual Reports Downloader
# ============================================================================
# Downloads historical USITC annual reports (FY 1917-2009) from the archive
# Source: https://www.usitc.gov/annual_reports_archive2
# ============================================================================

# Configuration
RESOURCES_DIR="reports"
BASE_URL="https://www.usitc.gov/publications/year_in_review"

# Create resources directory if it doesn't exist
mkdir -p "$RESOURCES_DIR"

echo "============================================================================"
echo "Downloading USITC Annual Reports (1917-2009)"
echo "============================================================================"
echo "Destination: $RESOURCES_DIR/"
echo ""

# Array of all PDF URLs (93 reports total)
declare -a REPORTS=(
    # 2009-2000 (Year in Review format)
    "pub4167.pdf"  # FY 2009
    "pub4093.pdf"  # FY 2008
    "pub4002.pdf"  # FY 2007
    "pub3915.pdf"  # FY 2006
    "pub3869.pdf"  # FY 2005
    "pub3759.pdf"  # FY 2004
    "pub3690.pdf"  # FY 2003
    "pub3594.pdf"  # FY 2002
    "pub3520.pdf"  # FY 2001
    "pub3445.pdf"  # FY 2000
    
    # 1999-1978 (Annual Report format with pub numbers)
    "pub3313.pdf"  # FY 1999
    "pub3193.pdf"  # FY 1998
    "pub3085.pdf"  # FY 1997
    "pub3025.pdf"  # FY 1996
    "pub2979.pdf"  # FY 1995
    "pub2873.pdf"  # FY 1994
    "pub2784.pdf"  # FY 1993
    "pub2624.pdf"  # FY 1992
    "pub2490.pdf"  # FY 1991
    "pub2354.pdf"  # FY 1990
    "pub2264.pdf"  # FY 1989
    "pub2140.pdf"  # FY 1988
    "pub2057.pdf"  # FY 1987
    "pub1935.pdf"  # FY 1986
    "pub1847.pdf"  # FY 1985
    "pub1718.pdf"  # FY 1984
    "pub1580.pdf"  # FY 1983
    "pub1412.pdf"  # FY 1982
    "pub1352.pdf"  # FY 1981
    "pub1084_b.pdf" # FY 1980
    "pub1084_a.pdf" # FY 1979
    "pub982.pdf"   # FY 1978
    
    # 1977-1961 (Annual Report format with pub numbers)
    "pub868.pdf"   # FY 1977
    "fy_1976_annual_report.pdf"  # FY 1976
    "fy_1975_annual_report.pdf"  # FY 1975
    "pub710.pdf"   # FY 1974
    "pub648.pdf"   # FY 1973
    "pub536.pdf"   # FY 1972
    "pub467.pdf"   # FY 1971
    "pub356.pdf"   # FY 1970
    "pub301.pdf"   # FY 1969
    "pub273.pdf"   # FY 1968
    "pub227.pdf"   # FY 1967
    "pub193.pdf"   # FY 1966
    "pub168.pdf"   # FY 1965
    "pub146.pdf"   # FY 1964
    "pub119.pdf"   # FY 1963
    "pub77.pdf"    # FY 1962
    "pub47.pdf"    # FY 1961
    
    # 1960-1917 (Annual Report format with year)
    "fy_1960_annual_report.pdf"
    "fy_1959_annual_report.pdf"
    "fy_1958_annual_report.pdf"
    "fy_1957_annual_report.pdf"
    "fy_1956_annual_report.pdf"
    "fy_1955_annual_report.pdf"
    "fy_1954_annual_report.pdf"
    "fy_1953_annual_report.pdf"
    "fy_1952_annual_report.pdf"
    "fy_1951_annual_report.pdf"
    "fy_1950_annual_report.pdf"
    "fy_1949_annual_report.pdf"
    "fy_1948_annual_report.pdf"
    "fy_1947_annual_report.pdf"
    "fy_1946_annual_report.pdf"
    "fy_1945_annual_report.pdf"
    "fy_1944_annual_report.pdf"
    "fy_1943_annual_report.pdf"
    "fy_1942_annual_report.pdf"
    "fy_1941_annual_report.pdf"
    "fy_1940_annual_report.pdf"
    "fy_1939_annual_report.pdf"
    "fy_1938_annual_report.pdf"
    "fy_1937_annual_report.pdf"
    "fy_1936_annual_report.pdf"
    "fy_1935_annual_report.pdf"
    "fy_1934_annual_report.pdf"
    "fy_1933_annual_report.pdf"
    "fy_1932_annual_report.pdf"
    "fy_1931_annual_report.pdf"
    "fy_1930_annual_report.pdf"
    "fy_1929_annual_report.pdf"
    "fy_1928_annual_report.pdf"
    "fy_1927_annual_report.pdf"
    "fy_1926_annual_report.pdf"
    "fy_1925_annual_report.pdf"
    "fy_1924_annual_report.pdf"
    "fy_1923_annual_report.pdf"
    "fy_1922_annual_report.pdf"
    "fy_1921_annual_report.pdf"
    "fy_1920_annual_report.pdf"
    "fy_1919_annual_report.pdf"
    "fy_1918_annual_report.pdf"
    "fy_1917_annual_report.pdf"
)

# Download counters
TOTAL=${#REPORTS[@]}
SUCCESS=0
SKIPPED=0
FAILED=0

echo "Found $TOTAL reports to download"
echo ""

# Download each report
for report in "${REPORTS[@]}"; do
    OUTPUT_FILE="$RESOURCES_DIR/$report"
    URL="$BASE_URL/$report"
    
    # Check if file already exists
    if [ -f "$OUTPUT_FILE" ]; then
        echo "⊘ SKIP: $report (already exists)"
        ((SKIPPED++))
        continue
    fi
    
    # Download the file
    echo "↓ Downloading: $report"
    if curl -f -L -o "$OUTPUT_FILE" "$URL" 2>/dev/null; then
        FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
        echo "  ✓ Success: $FILE_SIZE"
        ((SUCCESS++))
    else
        echo "  ✗ Failed: Could not download"
        rm -f "$OUTPUT_FILE"  # Remove partial file if download failed
        ((FAILED++))
    fi
    
    # Small delay to be polite to the server
    sleep 0.5
done

echo ""
echo "============================================================================"
echo "Download Summary"
echo "============================================================================"
echo "Total reports:      $TOTAL"
echo "Successfully downloaded: $SUCCESS"
echo "Already existed:    $SKIPPED"
echo "Failed:             $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✓ All downloads completed successfully!"
else
    echo "⚠ Some downloads failed. You may want to retry."
fi

echo ""
echo "Reports saved to: $RESOURCES_DIR/"
echo ""

# List the downloaded files
if [ $SUCCESS -gt 0 ] || [ $SKIPPED -gt 0 ]; then
    echo "Listing downloaded files:"
    ls -lh "$RESOURCES_DIR"/*.pdf 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
fi

echo ""
echo "============================================================================"
