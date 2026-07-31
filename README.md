# Drive Finance Data Analysis

Standalone data analysis assessment for the Drive Finance dataset (no chatbot, API, or LLM).

Explores 10 CSVs against the provided ERD, answers the required business questions, surfaces one original insight, and packages a short stakeholder summary with charts.

**Analysis as-of date:** 2026-07-30

---

## Quick start

```powershell
cd "d:\Projects\Drive Finance Data Analysis"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Run the full pipeline (regenerates charts + executive summary):**

```powershell
python -m src.run_analysis
```

**Or open the notebook:**

```powershell
jupyter notebook notebooks\drive_finance_analysis.ipynb
```

Then **Kernel → Restart & Run All**.

---

## Project layout

```text
Drive Finance Data Analysis/
├── *.csv                              # Input data (10 tables)
├── ERD Diagram.png                    # Canonical data model
├── Drive_Finance_Data_Analysis_Assessment.pdf
├── requirements.txt
├── NOTES.md                           # Tools used and why
├── FINDINGS.md / FINDINGS.pdf         # Plain-language findings
├── FUNCTIONS.md / FUNCTIONS.pdf       # Function reference
├── README.md
├── src/
│   ├── load_data.py                   # CSV loading & typing
│   └── run_analysis.py                # EDA, Q1–Q5, insight, summary
├── notebooks/
│   └── drive_finance_analysis.ipynb   # Full narrative analysis
└── outputs/
    ├── executive_summary.md           # 1-page stakeholder write-up
    └── charts/                        # Generated PNGs
```

---

## What the analysis covers

| Part | Content |
|------|---------|
| **1. EDA** | ERD mapping, shapes, nulls, duplicates, outliers, FK orphans, distributions |
| **2. Business questions** | Portfolio health, territories, KPI performers & target fairness, overdue installments, early-risk signals |
| **3. Original insight** | Credit score alone is a weak Delayed predictor; PTI and rate matter more |
| **4. Communication** | Executive summary + charts |

**Q2 assumption:** The assessment PDF truncates at “over- and under-”; we interpret this as territories over- vs under-performing on disbursement volume and collection/overdue quality.

---

## Main outputs

| Output | Path |
|--------|------|
| Stakeholder summary | `outputs/executive_summary.md` |
| Charts | `outputs/charts/*.png` |
| Findings guide | `FINDINGS.pdf` |
| Function docs | `FUNCTIONS.pdf` |

---

## Requirements

See `requirements.txt` (pandas, numpy, matplotlib, seaborn, jupyter, nbconvert, openpyxl).

Why these tools: `NOTES.md`.
