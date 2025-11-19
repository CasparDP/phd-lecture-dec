# Some Analyses for the PhD lecture
# Let's hope this works!

# Load libraries
source(here::here("data-prep", "Scripts", "load_libraries.R"))

# Connect to DuckDB
duckdb_conn <- dbConnect(duckdb::duckdb(),
  dbdir = here::here("data-prep", "DB", "jones_duckdb"),
  read_only = FALSE
)

# Load data

## Load import relief investigations - raw data
investigations <- tbl(duckdb_conn, "cleaned_usitc_import_injury") %>%
  collect()
# read_csv(here::here("data-prep", "cleaned_usitc_import_injury.csv"))

## Load matched import relief investigations - cleaned data
matched_investigations <- read_csv(here::here("data-prep", "safeguard_matches.csv")) %>%
  # TOFIX: Manually check these codes
  filter(best_match_NAICS != 99999) %>%
  # Innerjoin NIACS names
  # Make three-digit NAICS codes for merging
  mutate(
    NAICS_3d = str_sub(best_match_NAICS, 1, 3),
    SIC_2 = str_sub(best_match_SIC, 1, 2),
    SIC_3 = str_sub(best_match_SIC, 1, 3)
  ) %>%
  select(investigation_id, case_title, NAICS_3d, SIC_2, SIC_3) %>%
  distinct()

## Combine data - investigations with matched NAICS codes

investigations_naics <- investigations %>%
  inner_join(matched_investigations, by = c(
    "investigation_id" = "investigation_id"
  )) %>%
  mutate(
    year_zero = lubridate::year(investigation_date),
    year_zero_month = lubridate::month(investigation_date)
  ) %>%
  # year_zero is the year of the investigation decision - see Jones (1990)
  select(investigation_id, case_title, NAICS_3d, SIC_2, SIC_3, year_zero, year_zero_month) %>%
  mutate(cohort = paste0(SIC_3, "_", year_zero)) %>%
  # industries 314, 332,514 get treated twice within a year - keep first occurrence only
  group_by(SIC_3) %>%
  mutate(diff_year_zero = year_zero - lag(year_zero, order_by = year_zero)) %>%
  ungroup() %>%
  # Exclude second industry treatment within same year or immediately following year
  filter(diff_year_zero > 1 | is.na(diff_year_zero)) %>%
  ungroup()

# Load Compustat data with Jones residuals

## Load Jones residuals
em <- tbl(duckdb_conn, "jones_residuals") %>%
  collect()
# em <- read_csv(here::here("data-prep", "jones_residuals.csv"))
# view(em)
## Build cohort of firms affected by import relief investigations around the event year

pancaka <- function(year, ind, data = em) {
  treated_cohort <- data %>%
    filter(
      between(fyear, year - 6, year + 6),
      sector_3 == ind
    ) %>%
    mutate(
      event_year = year,
      time = fyear - year,
      #  # Adjust year_zero for investigations to align with fiscal years (fyear) in Compu
      #  time = case_when(month(datadate) < 7 ~ fyear - year,
      #                   TRUE ~ fyear - year + 1),
      cohort = paste0(ind, "_", year),
      treated = 1
    )
  message("Number of treated firm-years in sector ", ind, " for year ", year, ": ", nrow(treated_cohort))

  control_cohort <- data %>%
    mutate(sic = str_sub(sic, 1, 1)) %>%
    filter(
      between(fyear, year - 6, year + 6),
      # Keep firms in same years but different industries as controls
      sic != str_sub(ind, 1, 1)
    ) %>%
    mutate(
      event_year = year,
      time = fyear - year,
      # Adjust year_zero for investigations to align with fiscal years (fyear) in Compu
      #  time = case_when(month(datadate) < 7 ~ fyear - year,
      #                   TRUE ~ fyear - year + 1),
      cohort = paste0(ind, "_", year),
      treated = 0
    )
  message("Number of control firm-years in sector ", ind, " for year ", year, ": ", nrow(control_cohort))

  # combine treated and control cohorts
  combined_cohort <- bind_rows(treated_cohort, control_cohort)
}


em_cohorts <- map2(
  investigations_naics$year_zero,
  investigations_naics$SIC_3,
  ~ pancaka(.x, .y, data = em)
) %>%
  bind_rows() %>%
  distinct() %>%
  group_by(gvkey, cohort) %>%
  # Drop if not at least one pre- and post-event year observation for a firm in the cohort
  filter(min(time) < 0, max(time) > 0) %>%
  ungroup()

# Drop cohorts with no treated firms after adjusting for timing
em_cohorts <- em_cohorts %>%
  group_by(cohort) %>%
  filter(max(treated) == 1) %>%
  ungroup()

# Delete all ever treated sectors from control group

em_cohorts %>%
  group_by(treated) %>%
  count()

em_cohorts <- em_cohorts %>%
  filter(!(treated == 0 & sector_2 %in% unique(em_cohorts$sector_2[em_cohorts$treated == 1])))

em_cohorts %>%
  filter(treated == 1) %>%
  group_by(time) %>%
  count()

em_cohorts <- em_cohorts %>%
  # Adjust for timing differences between investigation and fiscal year ends
  inner_join(investigations_naics %>% select(cohort, year_zero_month), by = "cohort") %>%
  # Make sure that year 0 is the year the regulator can observe the fiscal year outcome
  mutate(time = case_when(
    # Fiscal year ends before investigation decision - no adjustment needed
    fyear == event_year & month(datadate) < year_zero_month ~ time,
    # Fiscal year ends after investigation decision - shift time by +1
    TRUE ~ time + 1
  )) %>%
  filter(between(time, -3, 3)) %>%
  distinct()

# Keep only firms with full data for all 7 years in the event window - Control group
em_cohorts <-
  em_cohorts %>%
  group_by(cohort, gvkey) %>%
  filter(treated == 1 | treated == 0 & n() == 7)



# Save dataset
write_csv(em_cohorts, here::here("data-prep", "em_cohorts.csv"))

# Save to DuckDB
dbWriteTable(duckdb_conn, "em_cohorts", em_cohorts, overwrite = TRUE)

# summary(em_cohorts$jones)
# plot(density(em_cohorts$jones, na.rm = TRUE))
# plot(em_cohorts$fyear, em_cohorts$jones)


# Make a bar plot of number of treated and control firms by time relative to event year
em_cohorts %>%
  group_by(time, treated) %>%
  summarise(num_firms = n_distinct(gvkey)) %>%
  ggplot(aes(x = time, y = num_firms, fill = as.factor(treated))) +
  geom_bar(stat = "identity", position = "dodge") +
  scale_x_continuous(breaks = seq(-3, 3, by = 1)) +
  labs(
    # title = "Number of Treated and Control Firms by Time Relative to Import Relief Investigation Year",
    title = "",
    x = "Years Relative to Investigation Year",
    y = "Number of Firms",
    fill = "Treated"
  ) +
  ggthemes::theme_hc()

# Save plot
ggsave(here::here("data-prep", "Figures", "number_of_firms_by_status.png"), width = 8, height = 6, dpi = 300)


# Summary statistics of Jones residuals by time relative to event year
em_cohorts %>%
  group_by(time, treated) %>%
  summarise(
    avg_jones = mean(jones, na.rm = TRUE),
    sd_jones = sd(jones, na.rm = TRUE)
  ) %>%
  pivot_wider(
    names_from = treated,
    values_from = c(avg_jones, sd_jones),
    names_prefix = "treated_"
  ) %>%
  arrange(time)
#  %>%
# print(n = Inf)

# Controls only form SIC 1


# Plot average Jones residuals around event year

em_cohorts %>%
  filter(treated == 1) %>%
  group_by(time) %>%
  summarise(avg_jones = mean(jones, na.rm = TRUE)) %>%
  ggplot(aes(x = time, y = avg_jones)) +
  geom_line(color = "darkgreen") +
  geom_point(color = "darkgreen") +
  geom_vline(xintercept = 0, linetype = "dashed", color = "lightblue") +
  geom_hline(yintercept = 0, linetype = "dashed", color = "lightblue") +
  scale_x_continuous(breaks = seq(-5, 5, by = 1)) +
  # Add grey rectangle for event year
  annotate("rect",
    xmin = -0.5, xmax = 0.5, ymin = -Inf, ymax = Inf,
    alpha = 0.2, fill = "lightgray"
  ) +
  labs(
    title = "Average Jones Residuals Around Import Relief Investigation Year",
    x = "Years Relative to Investigation Year",
    y = "Average Jones Residual"
  ) +
  ggthemes::theme_hc()

# Save plot
ggsave(here::here("data-prep", "Figures", "avg_jones_residuals_import_relief_simple.png"), width = 8, height = 6, dpi = 300)

# Plot average Jones residuals around event year for treated and control firms

em_cohorts %>%
  group_by(time, treated) %>%
  summarise(avg_jones = mean(jones, na.rm = TRUE)) %>%
  ggplot(aes(x = time, y = avg_jones, color = as.factor(treated))) +
  geom_line() +
  geom_point() +
  geom_vline(xintercept = 0, linetype = "dashed", color = "lightblue") +
  geom_hline(yintercept = 0, linetype = "dashed", color = "lightblue") +
  scale_x_continuous(breaks = seq(-5, 5, by = 1)) +
  # Add grey rectangle for event year
  annotate("rect",
    xmin = -0.5, xmax = 0.5, ymin = -Inf, ymax = Inf,
    alpha = 0.2, fill = "lightgray"
  ) +
  labs(
    title = "Average Jones Residuals Around Import Relief Investigation Year",
    x = "Years Relative to Investigation Year",
    y = "Average Jones Residual",
    color = "Treated"
  ) +
  ggthemes::theme_hc()

# Save plot
ggsave(here::here("data-prep", "Figures", "avg_jones_residuals_import_relief_did.png"), width = 8, height = 6, dpi = 300)


em_cohorts %>%
  # Identify SIC 1 for each cohort
  mutate(cohort_sic1 = str_sub(cohort, 1, 1), sector_1 = str_sub(sic, 1, 1)) %>%
  # select(treated, cohort, cohort_sic1, sector_1, sic) %>%
  # Limit control group to SIC 1 only
  filter(treated == 1 | (treated == 0 & sector_1 == cohort_sic1)) %>%
  group_by(time, treated) %>%
  summarise(avg_jones = mean(jones, na.rm = TRUE)) %>%
  ggplot(aes(x = time, y = avg_jones, color = as.factor(treated))) +
  geom_line() +
  geom_point() +
  geom_vline(xintercept = 0, linetype = "dashed", color = "lightblue") +
  geom_hline(yintercept = 0, linetype = "dashed", color = "lightblue") +
  scale_x_continuous(breaks = seq(-5, 5, by = 1)) +
  # Add grey rectangle for event year
  annotate("rect",
    xmin = -0.5, xmax = 0.5, ymin = -Inf, ymax = Inf,
    alpha = 0.2, fill = "lightgray"
  ) +
  labs(
    title = "Average Jones Residuals Around Import Relief Investigation Year",
    x = "Years Relative to Investigation Year",
    y = "Average Jones Residual",
    color = "Treated"
  ) +
  ggthemes::theme_hc()


# Plot average Jones residuals around event year: mean in thick black line and cohorts' means in light gray lines

avg_cohorts <- em_cohorts %>%
  filter(treated == 1) %>%
  group_by(cohort, time) %>%
  summarise(avg_jones = mean(jones, na.rm = TRUE)) %>%
  ungroup()

avg_em_all <- em_cohorts %>%
  filter(treated == 1) %>%
  group_by(time) %>%
  summarise(avg_jones = mean(jones, na.rm = TRUE)) %>%
  ungroup()

ggplot() +
  geom_line(
    data = avg_em_all,
    aes(x = time, y = avg_jones),
    color = "darkgreen", alpha = 0.5
  ) +
  geom_line(
    data = avg_cohorts,
    aes(x = time, y = avg_jones, group = cohort),
    color = "gray", alpha = 0.3
  ) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "lightblue") +
  geom_hline(yintercept = 0, linetype = "dashed", color = "lightblue") +
  annotate("rect",
    xmin = -0.5, xmax = 0.5, ymin = -Inf, ymax = Inf,
    alpha = 0.2, fill = "lightgray"
  ) +
  scale_x_continuous(breaks = seq(-5, 5, by = 1)) +
  labs(
    title = "Average Jones Residuals Around Import Relief Investigation Year",
    x = "Years Relative to Investigation Year",
    y = "Average Jones Residual"
  ) +
  ggthemes::theme_hc()

# Save plot
ggsave(here::here("data-prep", "Figures", "avg_jones_residuals_import_relief.png"), width = 8, height = 6, dpi = 300)

## Calculate first difference for Jones residuals around event year
em_did <- em_cohorts %>%
  group_by(gvkey, cohort) %>%
  mutate(jones_diff = jones - lag(jones, order_by = time)) %>%
  ungroup()

# Write to DuckDB
dbWriteTable(duckdb_conn, "em_did", em_did, overwrite = TRUE)

# Estimate first-difference DiD model for each time period, i.e. -2, -1, 0, 1


map(-2:1, ~ feols(jones_diff ~ treated | fyear + cohort,
  data = em_did %>% filter(time == .x)
) %>%
  summary(cluster = ~ cohort^gvkey) %>%
  # Extract coefficient and confidence intervals
  broom::tidy() %>%
  filter(term == "treated") %>%
  mutate(time = .x)) %>%
  bind_rows() %>%
  select(time, estimate, std.error) %>%
  mutate(time = factor(time, levels = -2:1)) %>%
  ggplot(aes(x = time, y = estimate)) +
  geom_point(color = "darkgreen", size = 3) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "lightblue", linewidth = 1.5) +
  # Add grey rectangle for event year
  annotate("rect",
    xmin = 2.5, xmax = 3.5, ymin = -Inf, ymax = Inf,
    alpha = 0.2, fill = "lightgray"
  ) +
  scale_x_discrete(breaks = -2:1, labels = c(
    expression(Delta[t - 2]), # Represents delta subscript 1
    expression(Delta[t - 1]), # Represents delta subscript 2
    expression(Delta[t = 0]), # Represents delta subscript 3
    expression(Delta[t + 1]) # Represents delta subscript 4
  )) +
  # Use standard errors to create error bars
  geom_errorbar(aes(ymin = estimate + std.error * -1.96, ymax = estimate + std.error * 1.96), width = 0.2, color = "darkgreen") +
  geom_hline(yintercept = 0, linetype = "dashed", color = "lightblue") +
  ylim(-0.05, 0.05) +
  labs(
    title = "Difference-in-Differences Estimates of Change in Jones Residuals Around Import Relief Investigations",
    x = "",
    y = "DiD Estimate of Change in Jones Residual (95% CI)"
  ) +
  ggthemes::theme_hc()


# Save plot
ggsave(here::here("data-prep", "Figures", "avg_jones_residuals_import_relief_first_diff.png"), width = 8, height = 6, dpi = 300)

# Disconnect from DuckDB
dbDisconnect(duckdb_conn, shutdown = TRUE)
