"""Seed seven reproducible snapshots. Final snapshot contains intentional errors."""
import os
from datetime import date, timedelta
import numpy as np
import psycopg


def main():
    rng = np.random.default_rng(20261118)
    start = date(2026, 11, 12)
    rows = []
    sectors = ["FINANCE", "CONSTRUCTION", "MANUFACTURING", "TECHNOLOGY", "RETAIL"]
    for offset in range(7):
        snap = start + timedelta(days=offset)
        for i in range(1000):
            borrower = f"BORR-{i:05d}"
            exposure = round(float(rng.lognormal(11, 0.7)), 2)
            pd_value = round(float(rng.uniform(0.001, 0.15)), 5)
            lgd = round(float(rng.uniform(0.1, 0.8)), 5)
            rating = int(rng.integers(1, 16))
            if offset == 6:
                if i < 30: pd_value = None  # 3% missing PD
                if i == 30: pd_value = 1.3
                if i == 31: lgd = -0.2
                if i == 32: rating = 99
                if i == 33: exposure = -100.0
                exposure *= 1.25  # drives ~25% portfolio-wide shift
            rows.append((snap, borrower, sectors[i % len(sectors)], exposure, pd_value, lgd, rating))
        if offset == 6:
            rows.append(rows[-1])  # duplicate borrower/date
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE alert_events, validation_runs, loan_portfolio RESTART IDENTITY CASCADE")
            with cur.copy("""COPY loan_portfolio (snapshot_date, borrower_id, sector, exposure,
                probability_of_default, loss_given_default, risk_rating) FROM STDIN""") as copy:
                for row in rows:
                    copy.write_row(row)
    print(f"Seeded {len(rows)} synthetic rows across seven snapshots. Final day has planted anomalies.")


if __name__ == "__main__":
    main()
