-- Executed ONCE when the PostgreSQL volume is first created.
CREATE DATABASE n8n;

CREATE TABLE IF NOT EXISTS loan_portfolio (
  record_id BIGSERIAL PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  borrower_id VARCHAR(40) NOT NULL,
  sector VARCHAR(80) NOT NULL,
  exposure NUMERIC(18,2) NOT NULL,
  probability_of_default DOUBLE PRECISION,
  loss_given_default DOUBLE PRECISION,
  risk_rating INTEGER
);
CREATE INDEX IF NOT EXISTS idx_portfolio_date ON loan_portfolio (snapshot_date);

CREATE TABLE IF NOT EXISTS validation_runs (
  run_id UUID PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  rows_checked INTEGER NOT NULL,
  status TEXT NOT NULL,
  issues_json JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_events (
  alert_id BIGSERIAL PRIMARY KEY,
  run_id UUID NOT NULL UNIQUE REFERENCES validation_runs(run_id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  payload JSONB NOT NULL
);
