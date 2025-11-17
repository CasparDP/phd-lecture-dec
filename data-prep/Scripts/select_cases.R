# Load libraries
source(here::here("data-prep", "Scripts", "load_libraries.R"))

# Connect to DuckDB
duckdb_conn <- dbConnect(duckdb::duckdb(), dbdir = "data-prep/DB/jones_duckdb", read_only = FALSE)

message("Connected to DuckDB")

message("Available tables in DuckDB: ", dbListTables(duckdb_conn))

# Clean and prepare USITC data
usitc_data <- tbl(duckdb_conn, "usitc_import_injury") %>%
    collect() %>%
    # read_csv("data-prep/usitc_import_injury.csv") %>%
    # TODO: Clean up in get_data.py by removing link column
    select(-link) %>%
    filter(
        !is.na(date),
        # Limit to investigations starting with TA-201 (safeguards) - Most of Jones (1990)/Safeguards/General Escape Clause
        str_detect(title, "TA-201")
    ) %>%
    # Make investigation ID column
    mutate(investigation_id = str_remove(title, "\\(.*\\)") %>%
        str_extract(., "TA-201-\\d+") %>%
        str_squish()) %>%
    filter(!is.na(investigation_id)) %>%
    group_by(investigation_id) %>%
    # Keep only the first occurrence of each investigation ID
    slice_min(order_by = date, n = 1) %>%
    ungroup() %>%
    # Make month and year variables
    mutate(investigation_date = lubridate::my(date)) %>%
    filter(year(investigation_date) >= 1980) %>%
    # Make clean title for LLM input
    mutate(clean_title = str_remove(title, ",.*") %>%
        str_squish())

# view(usitc_data)

# Save cleaned data
write_csv(usitc_data, "data-prep/cleaned_usitc_import_injury.csv")

# Save to DuckDB
dbWriteTable(duckdb_conn, "cleaned_usitc_import_injury", usitc_data, overwrite = TRUE)


# Make file for LLM RA
llm_input <- usitc_data %>%
    select(clean_title, investigation_id)

write_csv(llm_input, "data-prep/llm_usitc_safeguards_input.csv")

# Save to DuckDB
dbWriteTable(duckdb_conn, "llm_usitc_safeguards_input", llm_input, overwrite = TRUE)

# Additional exploration plots for slides

# read_csv("data-prep/usitc_import_injury.csv") %>%
#     filter(!is.na(date)) %>%
#     mutate(year = str_extract(date, "\\d{4}") %>% as.numeric()) %>%
#     group_by(type) %>%
#     count()


tbl(duckdb_conn, "usitc_import_injury") %>%
    collect() %>%
    filter(!is.na(date)) %>%
    mutate(year = str_extract(date, "\\d{4}") %>% as.numeric()) %>%
    filter(type == "Import Injury", year > 1979) %>%
    group_by(subject) %>%
    count(., sort = T) %>%
    ungroup() %>%
    slice_max(n = 5, order_by = n) %>%
    ggplot(aes(x = reorder(subject, n), y = n)) +
    geom_col() +
    coord_flip() +
    labs(
        x = "Subject", y = "Number of Investigations",
        title = "Top 5 Subjects of USITC Import Injury Investigations\n (1980 onwards)"
    ) +
    ggthemes::theme_hc()

# Save figure for slides
ggsave(here::here("data-prep", "figures", "usitc_top5_subjects.png"), width = 6, height = 4)

dbDisconnect(duckdb_conn, shutdown = TRUE)
