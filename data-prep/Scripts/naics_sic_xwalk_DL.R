# This file downloads and prepares the NAICS to DLI crosswalk data

base_url  <- "https://www2.census.gov/library/reference/naics/technical-documentation/concordance/"
xwalk_files  <- c("1987_sic_to_1997_naics.xls"
)

download.file(
  paste0(base_url, xwalk_files),
  destfile = paste0("data-prep/", xwalk_files),
  mode = "wb"
)

message("Downloaded: ", xwalk_files)