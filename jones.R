# Jennifer J. Jones Idea - TODAY
library(tidyverse)

# Identify import relief investigations -  USITC website

# Source: https://www.usitc.gov/commission_publications_library
# Information on Publication Types
# Trade Remedy
# Trade remedy publications concern subsidies (countervailing duties), sales at less than fair value (antidumping) and import surges (safeguards).
# Import Injury
# Import Injury publications concern antidumping (AD), countervailing duty (CVD), reviews (five-year sunset) and global/bilateral safeguards.
# General Factfinding
# General Factfinding publications concern probable effect studies, industry assessments and negotiation background information.
# Tariff
# Tariff publications include the Harmonized Tariff Schedule of the United States and proposed modifications to the Harmonized Tariff Schedule of the United States.
# Other
# Other publications are publications that fall outside of the above categories.

usitc_data <- read_csv("~/Dropbox/Github Data/phd-lecture-dec/commission_publications_lib/usitc_import_injury_crosswalk_full.csv")
# Clean and prepare USITC data
usitc_data <- usitc_data %>%
    filter(
        !is.na(industry),
        !is.na(date),
        type == "Import Injury",
        # Limit to AD/CVD investigations - Antidumping and Countervailing Duty
        subject == "AD/CVD" | subject == "Safeguards",
        # Keep only final investigations
        !str_detect(title, "\\(Preliminary\\)")
    ) %>%
    # make month and year variables
    mutate(investigation_date = lubridate::my(date)) %>%
    filter(year(investigation_date) <= 2022)

view(usitc_data)

x <- usitc_data %>%
    select(subject) %>%
    count(subject) %>%
    distinct()
view(x)

# Limit to safeguards investigations - most of Jones (1990)

# Read reports and find firm names - Jones (1990) approach

# Link NAICS or SIC codes to segment files - Incentives to manage earnings

# Link NAICS or SIC codes to Compustat firms - single segment firms

# Limit to US firms with primarily domestic operations

# Identify treated firms and time period around investigations, e.g 2 years before and after
