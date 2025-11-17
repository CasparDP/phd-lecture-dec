# Load libraries if not already loaded

# Install required packages if not already installed
required_packages <- c(
  "tidyverse", "dbplyr", "RPostgres", "duckdb", "fixest", "ggthemes",
  "DBI", "ggfixest", "kableExtra", "webshot2", "skimr", "here", "kableExtra"
)
new_packages <- required_packages[!(required_packages %in% installed.packages()[, "Package"])]
if (length(new_packages)) install.packages(new_packages)

# Load libraries
library(RPostgres)
library(tidyverse)
library(DBI)
library(dbplyr)
library(duckdb)
library(dbplyr)
library(fixest)
library(here)
# For nicer event study graphs
library(ggfixest)
# Optional for nicer html table
library(kableExtra)

# Setup DuckDB connection

# Make a duckDB connection in the DB Folder
message("Connecting to duckDB...")

if (!dir.exists("data-prep/DB")) {
  dir.create("data-prep/DB", recursive = TRUE)
}

message("DuckDB connection established, here: data-prep/DB/jones_duckdb")

# Connect to duckDB
duckdb_conn <- dbConnect(duckdb::duckdb(),
  dbdir = "data-prep/DB/jones_duckdb",
  read_only = FALSE
)

# Check if the connection is valid
if (DBI::dbIsValid(duckdb_conn)) {
  message("DuckDB connection is valid. ✅")
} else {
  stop("DuckDB connection is not valid. ❌")
}

# Disconnect from DuckDB
dbDisconnect(duckdb_conn, shutdown = TRUE)

# Make sure to adjust the "secret-example.csv" file with your own credentials

message("Don't forget to load database connection settings from 'secret-example.csv'")
