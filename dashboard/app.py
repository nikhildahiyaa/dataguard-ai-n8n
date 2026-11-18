"""Read-only DataGuard monitoring dashboard backed by the existing FastAPI API."""
from __future__ import annotations

import os
from collections import Counter
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE = os.getenv("DATAGUARD_API_URL", "http://api:8000").rstrip("/")

st.set_page_config(page_title="DataGuard | Data Quality", page_icon="🛡️", layout="wide")


def get_records(path: str, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch a bounded set of recent audit entries; timeout avoids UI hanging."""
    response = requests.get(f"{API_BASE}/{path}", params={"limit": limit}, timeout=12)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected API response for {path}: expected a list")
    return data


def flatten_issues(runs: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per reported rule violation, retaining its run and date."""
    records = []
    for run in runs:
        raw = run.get("issues_json") or []
        if not isinstance(raw, list):
            continue
        for issue in raw:
            if not isinstance(issue, dict):
                continue
            records.append({
                "run_id": str(run.get("run_id", "")),
                "snapshot_date": str(run.get("snapshot_date", "")),
                "executed_at": str(run.get("created_at", "")),
                "type": str(issue.get("type", "unknown")),
                "severity": str(issue.get("severity", "unknown")).lower(),
                "count": int(issue.get("count") or 0),
                "detail": str(issue.get("detail", "")),
            })
    return pd.DataFrame(records, columns=[
        "run_id", "snapshot_date", "executed_at", "type", "severity", "count", "detail"
    ])


def to_run_frame(runs: list[dict[str, Any]]) -> pd.DataFrame:
    if not runs:
        return pd.DataFrame(columns=["run_id", "snapshot_date", "created_at", "rows_checked", "status", "issue_count"])
    result = pd.DataFrame(runs)
    result["issue_count"] = result["issues_json"].map(
        lambda values: len(values) if isinstance(values, list) else 0
    )
    result["created_at"] = pd.to_datetime(result["created_at"], utc=True, errors="coerce")
    return result


st.title("🛡️ DataGuard AI")
st.caption("Local-first monitoring · Synthetic loan portfolio · No paid AI API required")

with st.sidebar:
    st.header("Controls")
    limit = st.slider("Recent validation runs", 10, 100, 100, step=10)
    st.caption("The existing API returns at most 100 runs per request.")
    st.button("↻ Refresh data", use_container_width=True)
    st.divider()
    st.caption("The dashboard is read-only. Run validations from n8n or FastAPI.")

try:
    runs = get_records("runs", limit)
    alerts = get_records("alerts", limit)
except (requests.RequestException, ValueError) as exc:
    st.error("Unable to load DataGuard API results. Make sure the API container is running.")
    st.code(str(exc))
    st.info("Check with: docker compose ps  |  curl http://localhost:8000/health")
    st.stop()

if not runs:
    st.info("No validation runs yet. Run the existing n8n workflow, or POST to /validate, then refresh.")
    st.stop()

run_df = to_run_frame(runs)
issue_df = flatten_issues(runs)
latest = runs[0]  # /runs is sorted by execution timestamp, newest first
latest_issues = latest.get("issues_json") or []

st.subheader("Latest validation run")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Rows checked", f"{int(latest.get('rows_checked', 0)):,}")
col2.metric("Rule violations", len(latest_issues))
col3.metric("High severity types", sum(x.get("severity") == "high" for x in latest_issues))
col4.metric("Status", str(latest.get("status", "unknown")).replace("_", " ").title())
st.caption(f"Snapshot: {latest.get('snapshot_date', 'unknown')} · Execution: {latest.get('created_at', 'unknown')}")

st.subheader("Latest run — seven anomaly types (when present)")
if latest_issues:
    latest_df = pd.DataFrame(latest_issues)
    latest_df["count"] = pd.to_numeric(latest_df["count"], errors="coerce").fillna(0)
    left, right = st.columns([2, 1])
    with left:
        fig = px.bar(latest_df.sort_values("count"), x="count", y="type", color="severity",
                     orientation="h", title="Affected count by validation rule",
                     category_orders={"severity": ["high", "medium", "low"]},
                     labels={"count": "Reported occurrences", "type": "Rule"},
                     hover_data=["detail"])
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        severity_counts = latest_df["severity"].value_counts().rename_axis("severity").reset_index(name="rule_types")
        fig2 = px.pie(severity_counts, names="severity", values="rule_types", hole=0.52,
                      title="Rule types by severity")
        fig2.update_layout(height=390, margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(latest_df[["type", "severity", "count", "detail"]],
                 use_container_width=True, hide_index=True)
    st.caption("Counts may overlap between rules and are not necessarily unique borrower records. An exposure shift is one portfolio-level event.")
else:
    st.success("No rule violations were recorded in the latest run.")

st.subheader("Historical validation trends")
left, right = st.columns(2)
with left:
    ordered = run_df.sort_values("created_at")
    fig = px.line(ordered, x="created_at", y="issue_count", markers=True,
                  hover_data=["snapshot_date", "rows_checked", "status"],
                  title="Number of failed validation rules per execution",
                  labels={"created_at": "Execution time (UTC)", "issue_count": "Failed rules"})
    st.plotly_chart(fig, use_container_width=True)
with right:
    by_day = run_df.groupby("snapshot_date", as_index=False).agg(
        executions=("run_id", "count"), failed_rules=("issue_count", "sum")
    ).sort_values("snapshot_date")
    fig = px.bar(by_day, x="snapshot_date", y="failed_rules", hover_data=["executions"],
                 title="Total failed rules by snapshot date (across executions)",
                 labels={"snapshot_date": "Snapshot date", "failed_rules": "Failed rules"})
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Re-running the same snapshot creates another audit run. Totals are not deduplicated.")

if not issue_df.empty:
    breakdown = (issue_df.groupby(["type", "severity"], as_index=False)
                 .agg(times_flagged=("run_id", "count"), total_reported_occurrences=("count", "sum"))
                 .sort_values("times_flagged", ascending=False))
    with st.expander("Historical anomaly breakdown", expanded=True):
        st.dataframe(breakdown, use_container_width=True, hide_index=True)

with st.expander("Validation run history", expanded=True):
    history = run_df[["created_at", "snapshot_date", "rows_checked", "status", "issue_count", "run_id"]].copy()
    st.dataframe(history, use_container_width=True, hide_index=True)
    st.download_button("Download run history (CSV)", history.to_csv(index=False).encode("utf-8"),
                       "dataguard-run-history.csv", "text/csv")

with st.expander("Stored alert events"):
    st.metric("Alerts in current API result window", len(alerts))
    if alerts:
        st.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
    else:
        st.caption("No alert events recorded yet.")

st.caption("Data comes from FastAPI GET /runs and GET /alerts. This dashboard does not query PostgreSQL directly.")
