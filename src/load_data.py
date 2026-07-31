"""Load Drive Finance CSVs with typed dates and clean optional FKs."""
# make the csv names like the ERD entity names

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

DATE_COLS: dict[str, list[str]] = {
    "employees": ["hire_date", "created_at"],
    "users": ["registration_date", "created_at"],
    "employee_customer_assignment": ["assigned_date"],
    "finance": ["approval_date", "created_at"],
    "loan": ["disbursement_date", "maturity_date", "created_at"],
    "installments": ["due_date", "payment_date"],
    "commissions": ["commission_date"],
    "employee_kpi": ["month"],
}

# Optional / nullable foreign keys (CEO has no manager; root territory has no parent)
NULLABLE_ID_COLS: dict[str, list[str]] = {
    "employees": ["manager_id"],
    "territories": ["parent_territory_id"],
}

TABLES = [
    "hierarchy_levels",
    "territories",
    "employees",
    "users",
    "employee_customer_assignment",
    "finance",
    "loan",
    "installments",
    "employee_kpi",
    "commissions",
]

# CSV filename -> ERD entity name
CSV_TO_ERD = {
    "hierarchy_levels": "hierarchy_levels",
    "territories": "territories",
    "employees": "employees",
    "users": "customers",
    "employee_customer_assignment": "customer_assignments", 
    "finance": "finance_applications",
    "loan": "loans",
    "installments": "installments",
    "employee_kpi": "employee_kpi",
    "commissions": "commissions",
}


def load_all(data_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir) if data_dir else ROOT
    frames: dict[str, pd.DataFrame] = {}
    for name in TABLES:
        path = data_dir / f"{name}.csv"
        df = pd.read_csv(path)
        for col in DATE_COLS.get(name, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        for col in NULLABLE_ID_COLS.get(name, []):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        frames[name] = df
    return frames
