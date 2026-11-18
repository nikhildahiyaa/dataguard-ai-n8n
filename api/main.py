from __future__ import annotations
import json
import os
import uuid
from datetime import date
from typing import Any

import pandas as pd
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from api.validation import validate_frame

app = FastAPI(title="DataGuard AI Validation API", version="0.1.0")


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


class ValidationRequest(BaseModel):
    snapshot_date: date | None = None


class AlertRequest(BaseModel):
    run_id: uuid.UUID
    snapshot_date: date
    status: str
    issues: list[dict[str, Any]]


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/validate")
def validate(payload: ValidationRequest):
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                if payload.snapshot_date is None:
                    cur.execute("SELECT MAX(snapshot_date) AS last_date FROM loan_portfolio")
                    last = cur.fetchone()["last_date"]
                else:
                    last = payload.snapshot_date
                if last is None:
                    raise HTTPException(status_code=409, detail="No data. Run the seed command first.")
                cur.execute("""SELECT snapshot_date, borrower_id, sector, exposure,
                         probability_of_default, loss_given_default, risk_rating
                         FROM loan_portfolio WHERE snapshot_date = %s""", (last,))
                records = cur.fetchall()
                cur.execute("""SELECT SUM(exposure) AS total FROM loan_portfolio
                        WHERE snapshot_date = (SELECT MAX(snapshot_date)
                            FROM loan_portfolio WHERE snapshot_date < %s)""", (last,))
                total = cur.fetchone()["total"]
                previous_exposure = float(total) if total is not None else None
                df = pd.DataFrame(records, columns=["snapshot_date", "borrower_id", "sector",
                    "exposure", "probability_of_default", "loss_given_default", "risk_rating"])
                issues = validate_frame(df, previous_exposure)
                result = {"run_id": str(uuid.uuid4()), "snapshot_date": last.isoformat(),
                          "status": "issues_found" if issues else "passed",
                          "rows_checked": len(df), "issue_count": len(issues), "issues": issues}
                cur.execute("""INSERT INTO validation_runs
                    (run_id, snapshot_date, rows_checked, status, issues_json)
                    VALUES (%s, %s, %s, %s, %s::jsonb)""",
                    (result["run_id"], last, len(df), result["status"], json.dumps(issues)))
                return result
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.post("/alerts", status_code=201)
def record_alert(payload: AlertRequest):
    """Persist an alert event. No external email/Slack account is required."""
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO alert_events (run_id, payload)
                    VALUES (%s, %s::jsonb) ON CONFLICT (run_id) DO NOTHING
                    RETURNING alert_id""", (payload.run_id, payload.model_dump_json()))
                row = cur.fetchone()
                return {"created": row is not None, "alert_id": row["alert_id"] if row else None}
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(status_code=404, detail="Unknown validation run") from exc


@app.get("/runs")
def list_runs(limit: int = 20):
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit must be 1–100")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT run_id, snapshot_date, created_at, rows_checked,
                status, issues_json FROM validation_runs ORDER BY created_at DESC LIMIT %s""", (limit,))
            return cur.fetchall()


@app.get("/alerts")
def list_alerts(limit: int = 20):
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit must be 1–100")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM alert_events ORDER BY created_at DESC LIMIT %s", (limit,))
            return cur.fetchall()
