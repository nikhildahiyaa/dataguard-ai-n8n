from __future__ import annotations
import pandas as pd


def validate_frame(df: pd.DataFrame, previous_exposure: float | None = None) -> list[dict]:
    """Deterministic checks; null PD/LGD handled separately from range violations."""
    issues: list[dict] = []
    n = len(df)
    if n == 0:
        return [{"type": "empty_snapshot", "severity": "high", "count": 0,
                 "detail": "No records were found for this snapshot."}]

    def add(kind: str, severity: str, count: int, detail: str):
        if count:
            issues.append({"type": kind, "severity": severity,
                           "count": int(count), "detail": detail})

    pd_missing = int(df["probability_of_default"].isna().sum())
    if pd_missing / n > 0.01:
        add("missing_pd", "high", pd_missing, f"{pd_missing}/{n} records have missing PD (>1%).")
    add("invalid_pd", "high", int((df["probability_of_default"].notna() &
        ~df["probability_of_default"].between(0, 1)).sum()), "PD must be between 0 and 1.")
    add("invalid_lgd", "high", int((df["loss_given_default"].notna() &
        ~df["loss_given_default"].between(0, 1)).sum()), "LGD must be between 0 and 1.")
    add("missing_lgd", "medium", int(df["loss_given_default"].isna().sum()), "LGD is missing.")
    add("duplicate_borrower", "medium", int(df.duplicated(
        subset=["snapshot_date", "borrower_id"], keep="first").sum()),
        "More than one row has the same borrower and snapshot date.")
    add("negative_exposure", "high", int((df["exposure"] < 0).sum()), "Exposure must be nonnegative.")
    add("invalid_rating", "medium", int((df["risk_rating"].isna() |
        ~df["risk_rating"].between(1, 15)).sum()), "Rating must be an integer in 1–15.")
    current_exposure = float(df["exposure"].sum())
    if previous_exposure is not None and previous_exposure > 0:
        pct_change = (current_exposure / previous_exposure - 1) * 100
        if abs(pct_change) > 15:
            add("exposure_shift", "medium", 1,
                f"Total exposure changed {pct_change:+.2f}% vs previous snapshot (>15%).")
    return issues
