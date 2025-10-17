# Load required libraries

library(duckdb)
library(tidyverse)

# # Check json data - something missing in DB?
# json <-
#     "/Users/casparm4/Dropbox/Github Data/phd-lecture-dec/DB/investigations.json" %>%
#     jsonlite::read_json(simplifyVector = TRUE) %>%
#     as_tibble()

# json$data %>%
#     pluck(7) %>%
#     as_tibble()

# # View all columns in the json data
# json$data %>%
#     as_tibble()  %>% names()

# Check ICT data database
# Make the path portable to your system
# Change the path below to your own path where you want to store the database
# For example: db_path <- '/path/to/your/Dropbox/Github Data/phd-lecture-dec/DB/ict_data.duckdb'
db_path <- "/Users/casparm4/Dropbox/Github Data/phd-lecture-dec/DB/ict_data.duckdb"


if (file.exists(db_path)) {
    con <- dbConnect(duckdb::duckdb(), dbdir = db_path, read_only = TRUE)
    tables <- dbListTables(con)
    print(paste("Database exists with tables:", paste(tables, collapse = ", ")))
    dbDisconnect(con, shutdown = TRUE)
} else {
    print("Database does not exist. Please run the download_ict.bash script to create it.")
}


# Connect to the database
con <- dbConnect(duckdb::duckdb(), dbdir = db_path)

# List all tables in the database
tables <- dbListTables(con)
print(tables)

investigations %>%
    group_by(investigation_type) %>%
    summarise(count = n()) %>%
    arrange(desc(count)) %>%
    print(n = Inf)

# Example query: Get all import injury investigations
investigations <- tbl(con, "ict_investigations_flat") %>%
    filter(investigation_type == "Import Injury") %>%
    collect()
view(investigations)

# Check investigation status data

investigations %>%
    group_by(investigation_status) %>%
    summarise(count = n()) %>%
    arrange(desc(count)) %>%
    print(n = Inf)

# Filter "Completed" investigations and view details
completed_investigations <- investigations %>%
    filter(
        investigation_status == "Completed",
        investigation_phase == "Final"
    )

view(completed_investigations)
# Bar chart of completed investigations by year
completed_investigations %>%
    mutate(year = lubridate::year(vote_date)) %>%
    group_by(year) %>%
    summarise(count = n()) %>%
    ggplot(aes(x = year, y = count)) +
    geom_bar(stat = "identity", fill = "steelblue") +
    labs(
        title = "Completed Import Injury Investigations by Year",
        x = "Year",
        y = "Number of Completed Investigations"
    ) +
    ggthemes::theme_hc()



dbDisconnect(con, shutdown = TRUE)
