# Jennifer J. Jones Idea - TODAY

# Load libraries
source(here::here("data-prep", "Scripts", "load_libraries.R"))


# Earnings management around import relief investigations - measure accruals using Jones (1991) model

# Load environment variables
user <- read_csv("secrets.csv")$user
pass <- read_csv("secrets.csv")$pass

wrds <- dbConnect(Postgres(),
    host     = "wrds-pgdata.wharton.upenn.edu",
    port     = 9737,
    user     = user,
    password = pass,
    sslmode  = "require",
    dbname   = "wrds",
    bigint   = "numeric"
)
wrds # checking if connection exists


# The composition of total accruals (TAt) is as follows:
# TAt = [ACurrent Assets
# Cash (1)] - [ACurrent Liabilities (5) - ACurrent Maturities of Long-Term Debt (44) -
# AIncome Taxes Payable (71)] - Depreciation and Amortization Expense (14), where the
# change (A) is computed between time t and time t - 1

# Inpiration comes from: https://gist.github.com/JoostImpink/8ce0af0a0a0bbb31c8e0 and https://github.com/joachim-gassen/explore_dacc/blob/master/run_me.R


us_firms <- tbl(wrds, I("comp.company")) %>%
    filter(
        loc == "USA",
        fic == "USA" # Filter to firms incorporated in the USA (excludes ADRs and foreign-incorporated firms)
    ) %>%
    select(conm, gvkey, loc, sic, spcindcd, ipodate, fic, weburl, naics) %>%
    collect() %>%
    # Need naics codes for linking to import relief investigations - refactor later
    filter(!is.na(sic), !between(as.numeric(sic), 6000, 6999)) %>%
    distinct() %>%
    # First two digits of SIC code for sector level analysis
    mutate(
        sector_2 = substr(sic, 1, 2),
        sector_3 = substr(sic, 1, 3),
        sector = substr(sic, 1, 4)
    )

message("Number of US firms with non-missing SIC codes in Compustat: ", nrow(us_firms %>% filter(!is.na(sic))))
message("Number of US firms with non-missing NAICS codes in Compustat: ", nrow(us_firms %>% filter(!is.na(naics))))

# Write to DuckDB for faster access later
duckdb_conn <- dbConnect(duckdb::duckdb(), dbdir = "data-prep/DB/us_firms_duckdb", read_only = FALSE)
# Save us_firms to DuckDB
dbWriteTable(duckdb_conn, "us_firms", us_firms, overwrite = TRUE)

# See Jones (1991) definition of total accruals:
# Total_Accruals = ((ACT - ACT_lag) - (CHE - CHE_lag)) - (LCT - LCT_lag) - DP

jones_ingredients <- tbl(wrds, I("comp.funda")) %>%
    filter(
        datadate >= as.Date("1975-01-01"),
        pddur == 12,
        indfmt == "INDL",
        datafmt == "STD",
        popsrc == "D",
        consol == "C",
        !is.na(at),
        at > 0
    ) %>%
    mutate(across(c(che, sale, rect), \(x) coalesce(x, 0))) %>%
    # Added sich
    select(gvkey, datadate, fyear, sich, at, ibc, oancf, sale, recch, ppegt, che, act, lct, dp, dlc) %>%
    collect() %>%
    group_by(gvkey) %>%
    # Compute variables needed for Jones (1991) model
    mutate(
        lagta = lag(at, 1, order = fyear), # lagged total assets
        tacc_jones = (((act - lag(act, 1, order = fyear)) - (che - lag(che, 1, order = fyear))) -
            ((lct - lag(lct, 1, order = fyear))) - dp) / lagta, # total accruals Jones definition
        tacc = (ibc - oancf) / lagta, # total accruals scaled by lagged total assets
        drev = (sale - lag(sale, 1, order = fyear)) / lagta, # change in revenue scaled by lagged total assets
        drevadj = (sale - lag(sale, 1, order = fyear)) / lagta - (recch - lag(recch, 1, order = fyear)) / lagta, # adjusted change in revenue by change in receivables scaled by lagged total assets
        ib = ibc, # net income before extraordinary items
        ib_l = lag(ibc, 1, order = fyear), # lagged net income before extraordinary items
        roa = ib / at,
        roa_l = ib_l / lagta, # net income before extraordinary items
        inverse_lagta = 1 / lagta, # inverse of lagged total assets
        ppe = ppegt / lagta
    ) # property, plant and equipment scaled by lagged total assets

# Save us_firms to DuckDB
dbWriteTable(duckdb_conn, "jones_ingredients", jones_ingredients, overwrite = TRUE)


# Inner join with US firms to limit to US firms only
jones_sample <- jones_ingredients %>%
    inner_join(us_firms, by = "gvkey")

# Delete duplicates if any
dubs <- jones_sample %>%
    group_by(gvkey, fyear) %>%
    filter(n() > 1) %>%
    count(gvkey)

message("Number of duplicate gvkeys in US firms: ", nrow(dubs))
rm(dubs)
# Drop missing values
jones_sample <- jones_sample %>%
    filter(!is.na(tacc_jones), !is.na(drev), !is.na(ppe), !is.na(inverse_lagta))

# # Drop sector years with less than 10 observations
jones_sample <- jones_sample %>%
    group_by(sector_3, fyear) %>%
    filter(n() >= 10) %>%
    ungroup()

# Winsorize variables to reduce influence of outliers

winsorize <- function(x, probs = c(0.01, 0.99), na.rm = TRUE) {
    qnt <- quantile(x, probs = probs, na.rm = na.rm)
    x[x < qnt[1]] <- qnt[1]
    x[x > qnt[2]] <- qnt[2]
    return(x)
}

# Summary statistics - before winsorization

jones_sample <- jones_sample %>%
    ungroup() %>%
    mutate(across(c(tacc_jones, tacc, drev, ppe, inverse_lagta), ~ winsorize(.x)))

# Summary statistics - after winsorization

jonez <- function(ind, year) {
    # Limit data to sector and year
    dataset <- jones_sample %>%
        filter(sector_3 == ind, fyear == year)

    # Estimate Jones (1991) model by sector and year - no constant
    model_jones <- feols(tacc_jones ~ inverse_lagta + drev + ppe - 1, data = dataset)
    # Get residuals
    residual <- broom::augment(model_jones, newdata = dataset)
    return(residual)
}

# Example usage
# jones_sample$sector_3 %>%
#     unique() %>%
#     sort()
# jonez("010", 2000) %>%
#     mutate(residual = tacc_jones - .fitted) %>%
#     select(residual, tacc_jones, .fitted)

# Apply jonez function to each sector and year combination
sector_years <- jones_sample %>%
    select(sector_3, fyear) %>%
    distinct()


jones_residuals <-
    map2(
        sector_years$sector_3, sector_years$fyear,
        ~ jonez(.x, .y)
    ) %>%
    bind_rows() %>%
    mutate(jones = tacc_jones - .fitted) # Adjusted Jones residual

write_csv(jones_residuals, "data-prep/jones_residuals.csv")

message("Disconnected from WRDS")
# Disconnect from WRDS
dbDisconnect(wrds)

# Save jones_residuals to DuckDB
dbWriteTable(duckdb_conn, "jones_residuals", jones_residuals, overwrite = TRUE)

# Verify table saved
tables <- dbListTables(duckdb_conn)
if ("jones_residuals" %in% tables) {
    message("jones_residuals table successfully saved to DuckDB. ✅")
} else {
    stop("Failed to save jones_residuals table to DuckDB. ❌")
}

# Disconnect from DuckDB
dbDisconnect(duckdb_conn, shutdown = TRUE)

# Finish message
message("Jones (1991) residuals calculation completed successfully.")
