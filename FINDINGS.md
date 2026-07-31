# Drive Finance — Findings Guide

Plain-language summary of everything the analysis found.  
**Analysis date:** 30 July 2026  
**Data:** 10 CSV tables (customers, employees, loans, installments, KPIs, etc.)

Charts live in `outputs/charts/`. Full code is in `notebooks/drive_finance_analysis.ipynb`.

---

## What the data covers

| Piece | Simple meaning | Scale |
|--------|----------------|-------|
| Customers (`users`) | People who applied / borrowed | 464 |
| Employees | Sales / collection staff | 104 |
| Finance applications | Loan applications | 420 |
| Loans | Approved & disbursed loans | 420 |
| Installments | Monthly payments due | ~12,300 |
| KPI + commissions | Performance numbers | Only **10** employees |

Not every employee has KPI data. When we talk about “top performers,” we only mean those 10 people.

---

## Data quality (what to trust / ignore)

A few conventions and quirks to know when reading the numbers:

1. **Days past due (`dpd`) can be negative — that is normal here**  
   Delayed loans often show a negative `dpd` (e.g. −29); Active/Closed are usually 0.  
   This is expected coding, not a data problem. Average DPD is reported alongside loan status.

2. **Maturity date looks wrong**  
   It is often only ~1 month after disbursement even when tenure is 36–48 months.  
   **Use instead:** `tenure_months`.

3. **Some empty fields are normal**  
   - CEO has no manager  
   - Root territory (Egypt) has no parent  
   - Unpaid installments have no payment date  

4. **ERD tables not in the CSVs**  
   Things like system users / roles exist on the diagram but were not provided — we ignored them.

5. **Duplicates / outliers**  
   No duplicate rows or duplicate primary keys in any CSV.  
   A few installment/outstanding amounts sit outside a simple IQR fence; they were **flagged, not removed**.

---

## Finding 1 — Overall loan portfolio health

**Question:** How healthy is the loan book?

| Status | Share (approx.) | Meaning |
|--------|------------------|---------|
| Active | ~2/3 | Still running |
| Closed | ~1/4 | Fully paid / finished |
| Delayed | ~10% (43 loans) | In trouble |

- **Total still owed (outstanding):** about **17.7 million**
- **Average DPD:** about **−3** overall (pulled down because Delayed loans use negative DPD, e.g. −29)
- About **1 in 10** loans is Delayed — that is the main risk signal in this extract.

**In one sentence:** The book is mostly fine, but a clear minority is already delayed; negative DPD on Delayed loans is expected and part of how this data encodes arrears.

---

## Finding 2 — Territories: who is big vs who is struggling

**Question:** Which territories over- and under-perform?  
*(Assumption: “over/under” means volume size and collection quality.)*

**Largest by money disbursed**

1. **Direct Sales**
2. **Egypt**

**Collection quality**

- **Worst (highest overdue rate):** Direct Sales  
- **Best (cleanest):** El Bahira  

**Takeaway**

- Big volume ≠ good quality. Direct Sales is both large and stressed.
- Smaller territories can still be quality problems even if they look small on volume.
- Volume leaders and quality leaders are not the same list.

---

## Finding 3 — Who performs well, and are targets fair?

**Question:** Top/bottom people from KPI + commissions; are targets fair?

**Coverage limit (important):**  
KPI and commission data exist for **only 10 employees**. We cannot rank the other 94.

**What we found**

- All 10 sit at roughly the **same target attainment (~87%)**.  
  So “who hit target” does **not** separate good from weak — targets look scaled to what people already achieved.
- **Collection rate** does separate them (best vs weakest differ by about **10 points**).
- Bigger targets tend to go with bigger books, **not** clearly with riskier books.

**In one sentence:** Rank these 10 by collection rate, not by “% of target”; and treat target fairness as mixed.

---

## Finding 4 — What overdue installments look like

**Question:** Who is already late on payments?

- **79** installments are past their due date and not fully paid (Partial or Pending).
- Overdues concentrate in **higher-volume territories**.
- They appear across **credit-score bands** — high score does not clearly protect someone in this data.

**In one sentence:** Arrears are real and clustered by territory/volume, not only among “low score” customers.

---

## Finding 5 — Early warning signals (before a loan becomes Delayed)

**Question:** What should we watch at the start of a loan?

Useful signals in this data:

1. **High payment-to-income (PTI)** — installment is large relative to salary (especially PTI > 0.5)
2. **High interest rate (≥ 16%)** — pricing already reflects higher risk
3. **Short tenure** — shorter loans in this book co-occur with more delay

**Practical rule:** Flag accounts that hit **2 or more** of these at origination for early follow-up.

Credit score alone is a weak separator here (see next section).

---

## Finding 6 — Original insight (most important)

**Credit score alone is a weak predictor of Delayed loans in this dataset.**

What that means in practice:

- Higher score bands do **not** cleanly show lower delay rates.
- **Affordability (PTI)** and **interest rate** carry more signal.
- A high score should not replace a payment-capacity check.

**Business implication:**  
Refresh underwriting / early-collections priority to weight income burden and pricing, not score alone.

---

## Simple action list

| Priority | Action |
|----------|--------|
| 1 | Watch Direct Sales for collection pressure (high volume + high overdue). |
| 2 | Read negative DPD on Delayed loans as expected coding; use status, DPD, and installment arrears together. |
| 3 | Rank the KPI cohort by **collection rate**, not target %. |
| 4 | Build a watchlist for high PTI + high rate + short tenure (2+ flags). |
| 5 | Do not treat credit score as a sufficient risk signal on its own. |

---

## Where to look next

| Want… | Open… |
|-------|--------|
| Short stakeholder memo | `outputs/executive_summary.md` |
| Charts | `outputs/charts/` |
| Full methods & code | `notebooks/drive_finance_analysis.ipynb` |
| Why these tools | `NOTES.md` |
| Re-run everything | `python -m src.run_analysis` from project root |
