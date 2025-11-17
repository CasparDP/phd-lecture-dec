# This script is for table styling and formatting using the etable package

# Table setup
dict <- setFixest_dict(
    c(
        jones_diff = "$\\Delta(DA_{it})$",
        injury_word_ratio_diff = "$\\Delta(IWR_{it})$",
        treated = "Treated",
        post = "Post",
        fyear = "Fiscal Year",
        cohort = "Cohort",
        gvkey = "Firm",
        SE = "Standard errors clustered by cohort x firm and reported in parentheses if not indicated otherwise in the table. *, **, and *** denote significance at 10%, 5%, and 1%, respectively."
    ),
    reset = TRUE
)

# For LaTeX/Beamer output (slides), use:
# my_style <- style.tex(
#     tpt = TRUE,
#     notes.tpt.intro = "\\tiny"
# )
# setFixest_etable(style.tex = my_style)

# For HTML output (website), specify style.html in the etable() call
setFixest_etable(markdown = TRUE)
