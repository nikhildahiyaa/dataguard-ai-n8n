from datetime import date
import pandas as pd
from api.validation import validate_frame


def test_detects_known_issues():
    df = pd.DataFrame([
        {"snapshot_date": date(2026, 11, 18), "borrower_id": "A", "exposure": 100,
         "probability_of_default": None, "loss_given_default": 0.4, "risk_rating": 2},
        {"snapshot_date": date(2026, 11, 18), "borrower_id": "A", "exposure": 100,
         "probability_of_default": 1.4, "loss_given_default": -0.1, "risk_rating": 99},
    ])
    types = {issue["type"] for issue in validate_frame(df, 100)}
    assert {"missing_pd", "invalid_pd", "invalid_lgd", "duplicate_borrower",
            "invalid_rating", "exposure_shift"}.issubset(types)


def test_clean_snapshot():
    df = pd.DataFrame([{"snapshot_date": date(2026, 11, 18), "borrower_id": "A",
        "exposure": 100, "probability_of_default": .02, "loss_given_default": .4,
        "risk_rating": 6}])
    assert validate_frame(df, 100) == []


def test_empty_snapshot():
    df = pd.DataFrame(columns=["snapshot_date", "borrower_id", "exposure",
        "probability_of_default", "loss_given_default", "risk_rating"])
    assert validate_frame(df)[0]["type"] == "empty_snapshot"
