# PhD Lecture: Earnings Management Then and Now: Revisiting Jones (1991)

**Subtitle:** Website Data, Replication, and Research Design

## Overview

- **Duration**: 2 hours
- **Structure**: Part 1 (40-50 min) + Part 2 (60-70 min)
- **Objective**: Introduce website data methodology, replicate Jones (1991) with modern methods, demonstrate the research process from replication to extension, and stimulate student creativity through structured critique

---

## Part 1: Three Papers (40-50 minutes)

### 1. Haans & Mertens (2024) - "The Internet Never Forgets" (10-15 min)

**Focus**: Method + Data Quality

- Wayback Machine + web scraping methodology
- CompuCrawl database (11,277 firms, 1996-2020)
- **Critical issues**: ~20% missing data per year, survivorship bias, coverage improves over time
- **Key resources**: Open source code, tutorial for longitudinal data collection
- **Takeaway #1**: _Website data offers unprecedented longitudinal access, BUT requires careful attention to coverage gaps and data quality_

### 2. Boulland et al. (2025) - "Company Websites: A New Measure of Disclosure" (10-15 min)

**Focus**: Disclosure Measurement + Validation

- Website-based disclosure measure (size + content categories)
- Validation: 0.12-0.30 correlations with traditional measures (10-K filings, management forecasts)
- Applications: information asymmetry, private equity deals, ESG compliance
- **Devil's advocate moment**: Low correlations = capturing new dimensions OR measurement noise?
- **Takeaway #2**: _Website-based measures complement traditional disclosure metrics BUT validity questions remain—interpret with caution_

### 3. Jones (1991) - "Earnings Management During Import Relief Investigations" (15-20 min)

**Focus**: Clean Research Setting + Identification Strategy

- ITC import relief process: profitability is explicit injury factor
- Unique incentive alignment: all parties benefit from appearing injured
- Jones model for discretionary accruals (foundation of earnings management literature)
- Firms manage earnings DOWN in investigation year (income-decreasing accruals)
- **What makes this exceptional**: Clear incentives, no sophisticated monitoring, powerful research design
- **Bridge to Part 2**: "In 1991, one financial statement served all audiences. Today, firms have rich web presence during investigations. What would Jennifer Jones do with website data?"

---

## Part 2: Research in Action (60-70 minutes)

**Approach**: Transparent expert modeling—showing the actual research process, including code, data challenges, and unresolved concerns

### Phase 1: The Replication Journey (20 minutes)

**What I Set Out to Replicate**

- Jones (1991) main finding using modern methods
- Cross-sectional vs time-series approach (and why it matters)

**Problem I Had to Solve Along the Way**

- Fiscal years ≠ calendar years ≠ investigation dates
- Mapping investigations to industries
- Instutional details of ITC process

**Live Demo: Replication Results** (via GitHub page)

- Sample construction and coverage
- Key results comparing to Jones Table 5
- Code walkthrough - if time permits

**Takeaways**: Replication validates methods, but what NEW insight can we add?

### Phase 2: Website Data Exploration (25 minutes)

**Hypothesis Development**

- Multi-channel disclosure strategy during investigations
- Possible mechanisms: injury narrative, audience-specific messaging

**What I Actually Did (Quick & Dirty)**

- Wayback Machine snapshots + keyword frequency analysis
- Event study around investigation dates
- Preliminary correlation with discretionary accruals

**Live Demo: Website Analysis** (via GitHub page)

- Keyword frequency trends
- Specific firm examples (TBD)
- Preliminary results
- Code walkthrough - if time permits

**What Keeps Me Up at Night: Serious Concerns**

### Phase 3: Structured Critique (20 minutes)

**Group Discussion (10 minutes)**

Students choose one of four prompts:

- **Prompt A: Concerns Triage** - Assess severity of concerns, identify if fixable
- **Prompt B: Design Improvements** - Propose one specific enhancement with 3 more months
- **Prompt C: Alternative Outcomes** - What else could you measure on websites beyond keywords?
- **Prompt D: The Pivot** - If website approach fails, what alternative data source?

**Class Discussion (10 minutes)**

- Groups share critiques

- **Takeaway**: Research is about evaluating trade-offs, not seeking perfection

### Phase 4: Wrap-Up (5 minutes)

**If I Were to Continue**

**Key Lessons**

- Replication builds foundation for extensions
- "Quick checks" before major investments
- All research has concerns—manage them, don't eliminate them
- Make your thinking process visible

---

## Materials Available

### Pre-Class Access

**Required:**

- All three papers (provided with reading guide)
- GitHub repository with code and documentation
- Jones replication page (complete analysis walkthrough)
- Website analysis page (preliminary exploration)

**Optional:**

- Students review code examples and prepare questions
- Students identify one recent import relief case to discuss

### In-Class Materials

**Part 1:**

- Slide deck with key exhibits, validation tables, devil's advocate discussions

**Part 2:**

- Live GitHub page demos (replication + website analysis)
- Actual R scripts (Jones model implementation)
- Actual Python scripts (Wayback Machine scraping)
- Structured critique prompts (handouts or shared doc)

### Repository Structure

```
/
├── README.md (this file)
├── code/
│   ├── jones_model.R (discretionary accruals estimation)
│   ├── scrape_wayback.py (website data collection)
│   └── ...
├── data/
│   ├── README.md (data dictionary)
│   ├── itc_cases.csv
│   └── ...
├── docs/
│   ├── jones-replication.html (full replication walkthrough)
│   ├── website-analysis.html (preliminary text analysis)
│   └── lecture_slides.html
└── assets/ (figures, images)
```

---

## Learning Objectives

By engaging with this lecture and materials, students should be able to:

1. **Understand archival website data methodology** (collection, coverage, quality issues)
2. **Evaluate disclosure measures critically** (validity, correlation interpretation, measurement trade-offs)
3. **Recognize clean research settings** (incentive alignment, institutional details matter)
4. **Apply replication thinking** (when and how to revisit classics with new data)
5. **Practice research design** (identify concerns, evaluate trade-offs, not perfection)
6. **Navigate iterative research** (quick checks → refinement → investment decisions)
7. **Generate own research ideas** by observing expert thinking patterns and adapting methods to new questions
8. **Engage creatively** with provided materials to stimulate curiosity and develop novel research directions

---

## Pedagogical Approach

This lecture uses **cognitive apprenticeship**—making expert thinking visible:

- **Transparency**: Show actual code, messy analyses, unresolved concerns
- **Process over product**: Research is iterative exploration, not linear perfection
- **Honest assessment**: "Here's what worries me" / "I don't know how to fix this yet"
- **Structured critique**: Students evaluate the work rather than generating from scratch
- **Decision-making**: Explicit narration of choices, trade-offs, and stopping points

**Goal**: Students learn by observing how an economist thinks through research problems, then practice those thinking patterns through structured engagement.

---

## Contact & Collaboration

**Instructor**: Caspar David Peter
**Email**: [peter@rsm.nl](mailto:peter@rsm.nl)
**Institution**: Rotterdam School of Management

Students interested in extending this research or exploring related questions are encouraged to reach out. The repository materials are designed to be adapted for your own research ideas.

---

## Acknowledgments

This lecture builds on the foundational work of:

- Jennifer J. Jones (1991) - for the original research design
- Haans & Mertens (2024) - for the web scraping methodology
- Boulland et al. (2025) - for website disclosure measures

All errors, half-baked ideas, and unresolved concerns in Part 2 are entirely my own.
