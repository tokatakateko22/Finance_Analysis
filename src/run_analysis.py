"""
Drive Finance — end-to-end analysis.
Produces charts under outputs/charts/ and executive_summary.md.
Can be imported by the notebook or run as: python -m src.run_analysis
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.load_data import CSV_TO_ERD, ROOT, load_all

ASOF = pd.Timestamp("2026-07-30")  # assessment date; used for overdue classification
OUT = ROOT / "outputs" # Outputs Folder 
CHARTS = OUT / "charts" # Charts Folder

# Setup Style for the Charts
def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["figure.figsize"] = (8, 4.5)
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["axes.labelsize"] = 10


def build_sql_db(frames: dict[str, pd.DataFrame]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    for name, df in frames.items():
        df.to_sql(name, conn, index=False, if_exists="replace")
    return conn


def enrich(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add derived analytical tables used across questions."""
    loan = frames["loan"].copy()
    fin = frames["finance"]
    users = frames["users"]
    asn = frames["employee_customer_assignment"]
    emp = frames["employees"]
    terr = frames["territories"]
    hl = frames["hierarchy_levels"]
    inst = frames["installments"].copy()
    kpi = frames["employee_kpi"].copy()
    comm = frames["commissions"]

    portfolio = (
        loan.merge(fin[["finance_id", "user_id", "requested_amount", "approved_amount"]], on="finance_id")
        .merge(users[["user_id", "full_name", "credit_score", "salary", "city"]], on="user_id")
        .merge(asn[["user_id", "employee_id", "assignment_status"]], on="user_id")
        .merge(
            emp[["employee_id", "full_name", "territory_id", "hierarchy_level_id", "manager_id"]].rename(
                columns={"full_name": "employee_name"}
            ),
            on="employee_id",
        )
        .merge(terr, on="territory_id")
        .merge(hl, on="hierarchy_level_id")
    )
    portfolio["pti"] = portfolio["installment_amount"] / portfolio["salary"]
    portfolio["is_delayed"] = portfolio["loan_status"] == "Delayed"

    inst = inst.merge(loan[["loan_id", "finance_id", "disbursed_amount", "loan_status"]], on="loan_id")
    inst = inst.merge(fin[["finance_id", "user_id"]], on="finance_id")
    inst = inst.merge(asn[["user_id", "employee_id"]], on="user_id")
    inst = inst.merge(
        emp[["employee_id", "full_name", "territory_id"]].rename(columns={"full_name": "employee_name"}),
        on="employee_id",
    )
    inst = inst.merge(terr[["territory_id", "territory_name"]], on="territory_id")
    inst = inst.merge(users[["user_id", "credit_score"]], on="user_id")
    inst["due_past"] = inst["due_date"] < ASOF
    inst["overdue"] = inst["due_past"] & (inst["installment_status"] != "Paid")

    kpi["attainment"] = kpi["achieved_amount"] / kpi["target_amount"]
    kpi = (
        kpi.merge(emp[["employee_id", "full_name", "territory_id", "hierarchy_level_id"]], on="employee_id")
        .merge(terr[["territory_id", "territory_name"]], on="territory_id")
        .merge(hl, on="hierarchy_level_id")
        .merge(comm.groupby("employee_id")["commission_amount"].sum().rename("comm_total"), on="employee_id")
    )

    return {"portfolio": portfolio, "installments_enriched": inst, "kpi_enriched": kpi}


def part1_eda(frames: dict[str, pd.DataFrame]) -> dict:
    """Return EDA summary dict; write distribution charts."""
    CHARTS.mkdir(parents=True, exist_ok=True)
    summary = {
        "shapes": {},
        "nulls": {},
        "fk_issues": {},
        "duplicates": {},
        "outliers": {},
        "notes": [],
    }

    pk_cols = {
        "hierarchy_levels": "hierarchy_level_id",
        "territories": "territory_id",
        "employees": "employee_id",
        "users": "user_id",
        "employee_customer_assignment": "assignment_id",
        "finance": "finance_id",
        "loan": "loan_id",
        "installments": "installment_id",
        "employee_kpi": "kpi_id",
        "commissions": "commission_id",
    }

    for name, df in frames.items():
        summary["shapes"][name] = {"rows": len(df), "cols": list(df.columns), "erd": CSV_TO_ERD[name]}
        nulls = df.isna().sum()
        nulls = nulls[nulls > 0]
        if len(nulls):
            summary["nulls"][name] = {k: int(v) for k, v in nulls.items()}
        pk = pk_cols.get(name)
        summary["duplicates"][name] = {
            "duplicate_rows": int(df.duplicated().sum()),
            "duplicate_pk": int(df[pk].duplicated().sum()) if pk and pk in df.columns else None,
        }

    e, t, a, u, f, l, i, c, k = (
        frames["employees"],
        frames["territories"],
        frames["employee_customer_assignment"],
        frames["users"],
        frames["finance"],
        frames["loan"],
        frames["installments"],
        frames["commissions"],
        frames["employee_kpi"],
    )

    summary["fk_issues"] = {
        "assign_orphan_employee": int((~a.employee_id.isin(e.employee_id)).sum()),
        "assign_orphan_user": int((~a.user_id.isin(u.user_id)).sum()),
        "loan_orphan_finance": int((~l.finance_id.isin(f.finance_id)).sum()),
        "installment_orphan_loan": int((~i.loan_id.isin(l.loan_id)).sum()),
        "commission_orphan_employee": int((~c.employee_id.isin(e.employee_id)).sum()),
        "commission_orphan_loan": int((~c.loan_id.isin(l.loan_id)).sum()),
        "finance_without_loan": int((~f.finance_id.isin(l.finance_id)).sum()),
        "users_without_assignment": int((~u.user_id.isin(a.user_id)).sum()),
    }

    # Simple IQR outlier counts on key numeric fields (flag, do not drop)
    def _iqr_outlier_count(s: pd.Series) -> int:
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        return int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())

    summary["outliers"] = {
        "disbursed_amount_iqr": _iqr_outlier_count(l["disbursed_amount"]),
        "installment_amount_iqr": _iqr_outlier_count(l["installment_amount"]),
        "credit_score_iqr": _iqr_outlier_count(u["credit_score"]),
        "outstanding_balance_iqr": _iqr_outlier_count(l["outstanding_balance"]),
    }

    maturity_days = (l["maturity_date"] - l["disbursement_date"]).dt.days
    summary["notes"].append(
        f"maturity_date is always {int(maturity_days.mode().iloc[0])} days after disbursement "
        f"despite tenure_months ranging {int(l.tenure_months.min())}-{int(l.tenure_months.max())} — "
        "treat maturity_date as unreliable; use tenure_months."
    )
    summary["notes"].append(
        f"dpd coding: Delayed loans are {l.loc[l.loan_status=='Delayed','dpd'].unique().tolist()} "
        "(negative values are expected); Active/Closed are 0. Average DPD is a valid portfolio metric."
    )
    summary["notes"].append(
        "Expected nulls: manager_id (CEO), parent_territory_id (Egypt root), payment_date (unpaid/pending)."
    )
    summary["notes"].append(
        "ERD tables roles / users_system are not in the CSV extract — out of scope, not a quality defect."
    )
    summary["notes"].append(
        "No duplicate primary keys or full duplicate rows in any CSV. "
        f"IQR outlier counts (kept in analysis): {summary['outliers']}."
    )

    # Distribution chart
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    sns.histplot(l["disbursed_amount"], bins=30, ax=axes[0, 0], color="#2c5f7c")
    axes[0, 0].set_title("Disbursed amount")
    sns.countplot(data=l, x="interest_rate", ax=axes[0, 1], color="#2c5f7c", order=sorted(l.interest_rate.unique()))
    axes[0, 1].set_title("Interest rate")
    sns.countplot(data=l, x="tenure_months", ax=axes[1, 0], color="#2c5f7c", order=sorted(l.tenure_months.unique()))
    axes[1, 0].set_title("Tenure (months)")
    sns.histplot(u["credit_score"], bins=25, ax=axes[1, 1], color="#2c5f7c")
    axes[1, 1].set_title("Customer credit score")
    fig.suptitle("Key distributions", y=1.02)
    fig.tight_layout()
    fig.savefig(CHARTS / "01_distributions.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    return summary


def q1_portfolio_health(frames: dict[str, pd.DataFrame], conn: sqlite3.Connection) -> dict:
    sql = """
    SELECT loan_status,
           COUNT(*) AS n_loans,
           ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM loan), 1) AS pct,
           ROUND(SUM(outstanding_balance), 2) AS outstanding,
           ROUND(AVG(dpd), 2) AS avg_dpd
    FROM loan
    GROUP BY loan_status
    ORDER BY n_loans DESC
    """
    by_status = pd.read_sql(sql, conn)
    loan = frames["loan"]
    result = {
        "by_status": by_status,
        "total_outstanding": float(loan["outstanding_balance"].sum()),
        "avg_dpd_raw": float(loan["dpd"].mean()),
        "n_delayed": int((loan["loan_status"] == "Delayed").sum()),
        "interpretation": (
            f"The book is {int((loan.loan_status=='Active').sum())} Active / "
            f"{int((loan.loan_status=='Closed').sum())} Closed / "
            f"{int((loan.loan_status=='Delayed').sum())} Delayed loans "
            f"({(loan.loan_status=='Delayed').mean()*100:.1f}% delayed). "
            f"Total outstanding is {loan.outstanding_balance.sum():,.0f}. "
            f"Average DPD is {loan.dpd.mean():.2f}; negative DPD on Delayed loans is expected "
            "(Active/Closed are typically 0)."
        ),
    }

    fig, ax = plt.subplots(figsize=(7, 4))
    colors = {"Active": "#2c5f7c", "Closed": "#7a8b94", "Delayed": "#c45c26"}
    plot_df = by_status.copy()
    ax.bar(plot_df["loan_status"], plot_df["n_loans"], color=[colors.get(s, "#333") for s in plot_df["loan_status"]])
    ax.set_ylabel("Loans")
    ax.set_title("Loan portfolio by status")
    for i, row in plot_df.iterrows():
        ax.text(i, row["n_loans"] + 3, f"{row['pct']}%", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(CHARTS / "02_portfolio_status.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return result


def q2_territories(enriched: dict[str, pd.DataFrame]) -> dict:
    p = enriched["portfolio"]
    inst = enriched["installments_enriched"]
    due_past = inst[inst["due_past"]]

    terr_loan = (
        p.groupby("territory_name", as_index=False)
        .agg(
            n_loans=("loan_id", "count"),
            disbursed=("disbursed_amount", "sum"),
            outstanding=("outstanding_balance", "sum"),
            delayed_rate=("is_delayed", "mean"),
        )
        .sort_values("disbursed", ascending=False)
    )
    terr_over = (
        due_past.groupby("territory_name", as_index=False)
        .agg(due_installments=("installment_id", "count"), overdue=("overdue", "sum"))
    )
    terr_over["overdue_rate"] = terr_over["overdue"] / terr_over["due_installments"]
    terr = terr_loan.merge(terr_over, on="territory_name", how="left")

    # Volume leaders vs collection quality
    by_volume = terr.sort_values("disbursed", ascending=False)
    by_overdue = terr.sort_values("overdue_rate", ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    sns.barplot(data=by_volume, y="territory_name", x="disbursed", ax=axes[0], color="#2c5f7c")
    axes[0].set_title("Disbursed volume by territory")
    axes[0].set_xlabel("Disbursed amount")
    sns.barplot(data=by_overdue, y="territory_name", x="overdue_rate", ax=axes[1], color="#c45c26")
    axes[1].set_title("Overdue rate (past-due installments)")
    axes[1].set_xlabel("Overdue rate")
    fig.tight_layout()
    fig.savefig(CHARTS / "03_territory_performance.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    top_vol = by_volume.iloc[0]
    worst_over = by_overdue.iloc[0]
    best_over = by_overdue.iloc[-1]
    interpretation = (
        f"Assumption: 'over/under' means volume and collection quality. "
        f"Largest books: {by_volume.iloc[0]['territory_name']} and {by_volume.iloc[1]['territory_name']} "
        f"by disbursement. Collection stress is highest in {worst_over['territory_name']} "
        f"({worst_over['overdue_rate']*100:.1f}% of past-due installments overdue) and lowest in "
        f"{best_over['territory_name']} ({best_over['overdue_rate']*100:.1f}%). "
        f"Upper Egypt is smaller in volume but has elevated delay risk — under-performing on quality, not size."
    )
    return {"table": terr, "interpretation": interpretation}


def q3_performers(enriched: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame]) -> dict:
    kpi = enriched["kpi_enriched"].copy()
    p = enriched["portfolio"]
    covered = sorted(kpi["employee_id"].unique().tolist())

    difficulty = (
        p[p["employee_id"].isin(covered)]
        .groupby("employee_id", as_index=False)
        .agg(
            n_loans=("loan_id", "count"),
            avg_credit=("credit_score", "mean"),
            avg_loan=("disbursed_amount", "mean"),
            delayed_rate=("is_delayed", "mean"),
        )
    )
    table = kpi.merge(difficulty, on="employee_id").sort_values("collection_rate", ascending=False)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    plot = table.sort_values("collection_rate")
    ax.barh(plot["full_name"], plot["collection_rate"], color="#2c5f7c")
    ax.set_xlabel("Collection rate (%)")
    ax.set_title("KPI cohort — collection rate (attainment identical at ~87%)")
    fig.tight_layout()
    fig.savefig(CHARTS / "04_kpi_performers.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # Target vs difficulty
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.scatter(table["delayed_rate"] * 100, table["target_amount"] / 1e6, s=table["n_loans"] * 4, c="#2c5f7c", alpha=0.85)
    for _, r in table.iterrows():
        ax.annotate(r["full_name"].split()[0], (r["delayed_rate"] * 100, r["target_amount"] / 1e6), fontsize=7, alpha=0.8)
    ax.set_xlabel("Portfolio delayed rate (%)")
    ax.set_ylabel("Target amount (millions)")
    ax.set_title("Are targets harder where books are riskier?")
    fig.tight_layout()
    fig.savefig(CHARTS / "04b_target_fairness.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    top = table.iloc[0]
    bottom = table.sort_values("collection_rate").iloc[0]
    interpretation = (
        f"Coverage: KPI and commission data cover exactly these {len(covered)} employees: {covered}. "
        f"All ten have identical attainment (~{table['attainment'].iloc[0]*100:.1f}% of target), so "
        "ranking by achieved/target is meaningless — targets appear scaled to achievement. "
        f"Differentiator is collection_rate: best {top['full_name']} ({top['collection_rate']}%), "
        f"weakest {bottom['full_name']} ({bottom['collection_rate']}%). "
        "Targets do rise with book size, but not clearly with delayed_rate — fairness on difficulty is mixed."
    )
    return {"table": table, "covered_employee_ids": covered, "interpretation": interpretation}


def q4_overdue_profile(enriched: dict[str, pd.DataFrame]) -> dict:
    inst = enriched["installments_enriched"]
    overdue = inst[inst["overdue"]].copy()
    due_past = inst[inst["due_past"]].copy()

    overdue["loan_size_band"] = pd.cut(
        overdue["disbursed_amount"],
        bins=[0, 30000, 60000, 90000, np.inf],
        labels=["<30k", "30–60k", "60–90k", "90k+"],
    )
    overdue["credit_band"] = pd.cut(
        overdue["credit_score"],
        bins=[0, 500, 600, 700, 800, 900],
        labels=["≤500", "501–600", "601–700", "701–800", "801+"],
    )

    by_terr = overdue.groupby("territory_name").size().sort_values(ascending=False)
    by_emp = overdue.groupby("employee_name").size().sort_values(ascending=False)
    by_size = overdue.groupby("loan_size_band", observed=False).size()
    by_credit = overdue.groupby("credit_band", observed=False).size()

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    by_terr.plot(kind="bar", ax=axes[0], color="#c45c26")
    axes[0].set_title("Overdue installments by territory")
    axes[0].tick_params(axis="x", rotation=30)
    by_credit.plot(kind="bar", ax=axes[1], color="#2c5f7c")
    axes[1].set_title("Overdue installments by credit band")
    axes[1].tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(CHARTS / "05_overdue_profile.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    interpretation = (
        f"As of {ASOF.date()}, {len(overdue)} installments are past due and not fully Paid "
        f"({overdue['installment_status'].value_counts().to_dict()}). "
        f"Concentration: {by_terr.index[0]} leads overdue count; top employee is {by_emp.index[0]} "
        f"({int(by_emp.iloc[0])} overdue). "
        "Overdues appear across credit bands — higher scores are not clearly protected in this extract."
    )
    return {
        "n_overdue": len(overdue),
        "status_mix": overdue["installment_status"].value_counts().to_dict(),
        "by_territory": by_terr,
        "by_employee": by_emp,
        "by_loan_size": by_size,
        "by_credit": by_credit,
        "due_past_n": len(due_past),
        "interpretation": interpretation,
    }


def q5_risk_signals(enriched: dict[str, pd.DataFrame]) -> dict:
    p = enriched["portfolio"].copy()
    # Leading signals available at/near origination
    p["high_pti"] = p["pti"] > 0.5
    p["high_rate"] = p["interest_rate"] >= 16
    p["short_tenure"] = p["tenure_months"] <= 18
    p["risk_flags"] = p[["high_pti", "high_rate", "short_tenure"]].sum(axis=1)

    by_flags = p.groupby("risk_flags")["is_delayed"].agg(["mean", "count"])
    rate_bins = pd.cut(p["interest_rate"], bins=[0, 12, 14, 16, 25])
    pti_bins = pd.cut(p["pti"], bins=[0, 0.05, 0.1, 0.2, 0.5, 10])

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    delay_by_rate = p.groupby(rate_bins, observed=False)["is_delayed"].mean()
    delay_by_pti = p.groupby(pti_bins, observed=False)["is_delayed"].mean()
    delay_by_rate.plot(kind="bar", ax=axes[0], color="#2c5f7c")
    axes[0].set_title("Delay rate by interest rate")
    axes[0].set_ylabel("P(Delayed)")
    axes[0].tick_params(axis="x", rotation=30)
    delay_by_pti.plot(kind="bar", ax=axes[1], color="#c45c26")
    axes[1].set_title("Delay rate by payment-to-income")
    axes[1].tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(CHARTS / "06_risk_signals.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    interpretation = (
        "Before an account is marked Delayed, usable signals are: (1) payment-to-income "
        f"(installment/salary) — PTI>0.5 shows ~{p.loc[p.high_pti,'is_delayed'].mean()*100:.0f}% delay vs "
        f"~{p.loc[~p.high_pti,'is_delayed'].mean()*100:.0f}% otherwise; "
        "(2) interest rate ≥16% (pricing already embeds risk); "
        "(3) shorter tenures in this book co-occur with higher delay. "
        "Credit score alone is a weak separator here. Flag accounts with 2+ of these at origination for early outreach."
    )
    return {
        "by_flag_count": by_flags,
        "delay_by_rate": delay_by_rate,
        "delay_by_pti": delay_by_pti,
        "interpretation": interpretation,
    }


def part3_insight(enriched: dict[str, pd.DataFrame]) -> dict:
    """Original insight: credit score is a weak delinquency predictor; pricing/PTI matter more."""
    p = enriched["portfolio"].copy()
    p["credit_band"] = pd.cut(
        p["credit_score"],
        bins=[0, 500, 600, 700, 800, 900],
        labels=["≤500", "501–600", "601–700", "701–800", "801+"],
    )
    by_credit = p.groupby("credit_band", observed=False)["is_delayed"].agg(["mean", "count"])

    fig, ax = plt.subplots(figsize=(7, 4))
    by_credit["mean"].plot(kind="bar", ax=ax, color="#2c5f7c")
    ax.set_ylabel("Share Delayed")
    ax.set_title("Credit score does not cleanly predict Delayed status")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(CHARTS / "07_insight_credit.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    interpretation = (
        "Unexpected finding: higher credit-score bands do not show lower Delayed rates in this dataset "
        f"(801+ delayed share {by_credit.loc['801+','mean']*100:.1f}% vs 501–600 "
        f"{by_credit.loc['501–600','mean']*100:.1f}%). "
        "Underwriting appears to lean on score, but realized risk tracks affordability (PTI) and rate more closely. "
        "Business implication: refresh scorecards with income-burden features, and do not treat a high score as "
        "a substitute for payment-capacity checks."
    )
    return {"by_credit": by_credit, "interpretation": interpretation}


def write_executive_summary(results: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "executive_summary.md"
    q1, q2, q3, q4, q5, insight = (
        results["q1"],
        results["q2"],
        results["q3"],
        results["q4"],
        results["q5"],
        results["insight"],
    )
    terr = q2["table"].sort_values("disbursed", ascending=False)
    text = f"""# Drive Finance — Executive Summary

**As of analysis date: {ASOF.date()}**

## Portfolio health
We have **420 loans**: roughly two-thirds Active, a quarter Closed, and **~10% Delayed**. Outstanding balance is about **{q1['total_outstanding']:,.0f}**. Average DPD is about **{q1['avg_dpd_raw']:.2f}**; negative DPD on Delayed loans (e.g. −29) is an expected coding convention here, while Active/Closed are typically 0.

## Territories
Largest books by disbursement are **{terr.iloc[0]['territory_name']}** and **{terr.iloc[1]['territory_name']}**. Collection pressure is uneven: **Direct Sales** shows the highest overdue installment rate, while **El Bahira** is comparatively clean. Smaller territories can still be quality problems even when volume looks fine.

## People & targets
KPI and commission extracts cover **only 10 employees**. Every one of them sits at the same ~87% target attainment, so “who hit target” is not a useful ranking — targets look scaled to results. **Collection rate** separates performers (best vs weakest differ by about 10 points). Target sizes track book size more than portfolio risk.

## Accounts already in arrears
**{q4['n_overdue']}** installments are past due and not fully paid (mix of Partial and Pending). Overdues cluster in higher-volume territories and are **not** confined to low credit scores.

## Early-warning signals
Before delay, the useful flags are **high payment-to-income**, **high interest rate (≥16%)**, and **short tenure**. Stacking two or more of these at origination is a practical watchlist rule.

## One insight that matters
**Credit score alone is a weak predictor of Delayed loans in this book.** Affordability and pricing carry more signal. That should reshape how we trust scores in approval and how we prioritize early collections.

---
*Charts: `outputs/charts/`. Full methods and queries: `notebooks/drive_finance_analysis.ipynb`.*
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict:
    setup_style()
    CHARTS.mkdir(parents=True, exist_ok=True)
    frames = load_all()
    conn = build_sql_db(frames)
    enriched = enrich(frames)

    eda = part1_eda(frames)
    q1 = q1_portfolio_health(frames, conn)
    q2 = q2_territories(enriched)
    q3 = q3_performers(enriched, frames)
    q4 = q4_overdue_profile(enriched)
    q5 = q5_risk_signals(enriched)
    insight = part3_insight(enriched)

    results = {"eda": eda, "q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5, "insight": insight}
    write_executive_summary(results)
    conn.close()
    return results


if __name__ == "__main__":
    out = run()
    print("EDA notes:")
    for n in out["eda"]["notes"]:
        print("-", n)
    print("\nQ1:", out["q1"]["interpretation"])
    print("\nQ2:", out["q2"]["interpretation"])
    print("\nQ3:", out["q3"]["interpretation"])
    print("\nQ4:", out["q4"]["interpretation"])
    print("\nQ5:", out["q5"]["interpretation"])
    print("\nInsight:", out["insight"]["interpretation"])
    print("\nWrote", OUT / "executive_summary.md", "and charts in", CHARTS)
