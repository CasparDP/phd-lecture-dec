# Earnings Management Then and Now: Revisiting Jones (1991)

Website Data, Replication, and Research Design

---

## What this lecture is about

This lecture explores how modern data sources can revisit a classic study on earnings management during import relief investigations.

- **Part 1 – Three papers**: Internet/Wayback data and CompuCrawl (`@haans2024internet`), website-based disclosure measures (`@boulland2025company`), and the original earnings management setting (`@jones1991earnings`).
- **Part 2 – Research in action**: A transparent walk-through of a Jones (1991) replication, a quick website text exploration, and a structured critique/brainstorming session.

Themes: replication, extending classic designs with new data, and practicing research design thinking.

---

## Quick links

- Slides: [lecture-slides](https://caspardp.github.io/phd-lecture-dec/lecture-materials/slides/lecture-slides.html)
- Lecture website/index: [index page](https://caspardp.github.io/phd-lecture-dec/)
- Jones replication: [Jones replication](https://caspardp.github.io/phd-lecture-dec/docs/jones-replication.html)
- Website analysis: [Website analysis](https://caspardp.github.io/phd-lecture-dec/docs/website-analysis.html)
- Paper summaries: [Paper summaries](https://caspardp.github.io/phd-lecture-dec/paper_summaries/)

---

## Part 1 – Three papers (high level)

- **`@haans2024internet` – The Internet Never Forgets**
  Wayback Machine + web scraping methodology; CompuCrawl database; focus on longitudinal website data and coverage/quality issues.
  _Takeaway_: Website data offers rich history, but coverage gaps and bias matter.

- **`@boulland2025company` – Company Websites: A New Measure of Disclosure**
  Website-based disclosure measures (size/content) and validation against traditional metrics; applications to information asymmetry and private firms.
  _Takeaway_: Website measures complement classic disclosure metrics.

- **`@jones1991earnings` – Earnings Management During Import Relief Investigations**
  Clean incentive setting at the ITC, the Jones model for discretionary accruals, and income-decreasing earnings management in the investigation year.
  _Bridge to Part 2_: What happens if we revisit this setting with modern data and tools?

---

## Part 2 – Research in action

- **Phase 1 – Replication**
  Revisit Jones (1991) with a modern sample and cross-sectional specification; handle timing (fiscal year vs. investigation dates) and sample construction; compare core results to the original.

- **Phase 2 – Website exploration**
  Quick-and-dirty keyword analysis on website text around investigations using archival data; check whether there is a signal; list major measurement and design concerns.

- **Phase 3 – Structured critique**
  Small-group prompts to triage concerns, propose design improvements, think of alternative website outcomes, or pivot to other data sources.

- **Wrap-up**
  Emphasis on replication as a starting point, quick checks before big investments, and making research decisions (go/no-go) explicit.

Details for each phase (timing, prompts, extra exhibits) live in the slides and HTML pages, not here.

---

## Using this repo

- **During the lecture**: Open the slides and the HTML pages (replication, website analysis, paper summaries) when prompted.
- **After the lecture**: Use the lecture website and HTML reports for full details on data sources, variable construction, and empirical results.
- **As a template**: Reuse the structure for your own projects (separate data prep, scripts, and rendered reports).

### Repository structure (high level)

- `index.qmd` – Landing page for the lecture website.
- `lecture-materials/` – Slides and handouts.
- `data-prep/` – Data cleaning, construction, and supporting scripts.
- `docs/` – Rendered HTML outputs (e.g. replication, website analysis, site pages).
- `assets/` – Figures, images, bibliographic files, styles.

More fine-grained documentation is available on the website/index page and inside the HTML reports.

---

## Reproducing the analysis

1. Clone this repository.
2. Follow the setup instructions on the lecture website/index page (packages, environment).
3. Use the Quarto/R/Python scripts referenced in the HTML reports to rerun the data prep and analyses.

The goal is that you can reproduce the results you see in class and adapt the code to your own questions.

---

## Learning goals

By the end of this lecture, you should be able to:

- Understand the potential and limitations of archival website data.
- Evaluate new disclosure measures critically.
- See how a classic setting (Jones 1991) can be revisited with modern data.
- Practice structured critique and research design thinking.
- Use this repo structure as a starting point for your own research projects.

---

## Contact

**Caspar David Peter**
Rotterdam School of Management
[peter@rsm.nl](mailto:peter@rsm.nl)

For questions, ideas, or potential extensions, feel free to reach out.

---

## License

This repository is made available under the MIT License. You are free to use, adapt, and extend the code and materials, provided that you include appropriate attribution.

---

## How to cite

If you use this repository or lecture materials in your own work or teaching, you can cite it as:

```bibtex
@misc{peter2025phdlecture,
  author       = {Caspar David Peter},
  title        = {Earnings Management Then and Now: Revisiting Jones (1991) -- Website Data, Replication, and Research Design},
  year         = {2025},
  howpublished = {GitHub repository},
  url          = {https://github.com/CasparDP/phd-lecture-dec}
}
```

---

## AI/LLM disclosure

AI tools (local and hosted LLMs) helped with brainstorming, structuring the lecture, and polishing some wording. The research ideas, empirical designs, and code are mine—any remaining errors are proudly human.
