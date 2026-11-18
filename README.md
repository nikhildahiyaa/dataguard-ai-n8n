# DataGuard AI — n8n + PostgreSQL + FastAPI

Portfolio-ready, local-first **synthetic** loan-data quality monitoring. Runs PostgreSQL,
FastAPI and n8n with Docker Compose; imports an n8n workflow that validates and logs
planted anomalies. No cloud AI account or Slack account is required for this MVP.

## Requirements

- Docker Desktop / Docker Engine with Compose v2
- 3 available local TCP ports: 5433 (Postgres), 8000 (API), 5678 (n8n)
- A terminal and a browser

## Quick start

1. Unzip this project and open a terminal inside `dataguard-ai-n8n/`.
2. Create `.env` from the sample:

   ```bash
   cp .env.example .env
   ```

3. **Edit `.env`** and replace `POSTGRES_PASSWORD` and `N8N_ENCRYPTION_KEY` with your own
   independent random secrets. For example, generate each secret with
   `python3 -c 'import secrets; print(secrets.token_hex(32))'`.
   Avoid special URI-reserved characters in `POSTGRES_PASSWORD` unless URL-encoded.
4. Start services:

   ```bash
   docker compose up -d --build
   docker compose ps
   ```

5. Generate deterministic test data (7,001 synthetic rows):

   ```bash
   docker compose run --rm seed
   ```

   **Warning:** The seed command intentionally resets portfolio, validation, and alert
   tables. Do not use it after creating data you wish to retain.
6. Test the validation endpoint:

   ```bash
   curl -s http://localhost:8000/health
   curl -s -X POST http://localhost:8000/validate \
     -H 'Content-Type: application/json' -d '{}'
   ```

   The second request should return `issues_found`, a `run_id`, and specific checks.

7. Open **http://localhost:5678**. Complete n8n's first-run local owner setup.
8. In n8n, import `workflows/daily_monitor.json` (workflow menu → Import from File).
9. Click **Execute workflow** using the Manual Trigger. It should reach
   **Persist Alert Event** on the `true` branch. The API logs a validation run and
   then persists a corresponding alert event in PostgreSQL.
10. Inspect results:

    ```bash
    curl -s http://localhost:8000/runs
    curl -s http://localhost:8000/alerts
    ```

11. To turn on daily monitoring, **publish/activate** the imported workflow in n8n.
    The Schedule Trigger targets 8 AM `America/Vancouver` by default; change `TZ`
    and the workflow's timezone together if needed. The schedule won't execute
    until the workflow is activated/published.

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Health check |
| POST | `/validate` | Analyze latest snapshot (`{}`) or `{"snapshot_date":"2026-11-18"}`; persist audit run |
| POST | `/alerts` | Persist alert event referencing an existing run |
| GET | `/runs` | Last 20 validation runs |
| GET | `/alerts` | Last 20 alert events |
| GET | `/docs` | Interactive OpenAPI docs |

## Run automated tests

```bash
docker compose run --rm --no-deps seed python -m pytest -q tests
```

Note: tests are **not** database integration tests; they verify deterministic validation logic.

## Architecture

```text
Manual Trigger ─┐
                ├─> HTTP POST /validate ─> IF issues_found ─┬─true─> HTTP POST /alerts
Daily 8 AM ─────┘                                           └─false─> End
                       FastAPI ↔ PostgreSQL
                       n8n   ↔ PostgreSQL (separate n8n database)
```

- PostgreSQL `dataguard` database stores synthetic portfolio, audit runs, alerts.
- PostgreSQL `n8n` database holds n8n workflows and credentials.
- `api/validation.py` performs deterministic checks; there are no LLM guesses.
- The n8n workflow uses Docker-network hostname `api`, not `localhost`.

## Checks

Missing PD (>1%), invalid PD, invalid LGD, missing LGD, duplicate borrower on
same day, negative exposure, invalid rating (assumed 1–15), and absolute portfolio
exposure movement (>15% vs previous snapshot). Rating bands and thresholds are
**demo assumptions**, not bank policy.

The final snapshot (2026-11-18) deliberately contains errors and a broad exposure
shift. Earlier days normally have clean samples. These are synthetic data only.

## Troubleshooting

- API not ready: `docker compose logs -f api postgres`
- n8n can't reach API: within n8n use `http://api:8000`, **not** `localhost:8000`.
- Database initialized without `n8n` database: SQL init scripts run only when
  the Postgres volume is first created. If starting fresh, run
  `docker compose down -v` **only if you agree to permanently erase ALL local data**,
  then `docker compose up -d --build` and seed again.
- n8n credentials missing after restart: keep `.env` and the `n8n_data` volume.
- On a conflict with port 5433, change the host-side binding only.
- To inspect the SQL tables:

  ```bash
  docker compose exec postgres psql -U dataguard -d dataguard -c \
    "SELECT snapshot_date, count(*) FROM loan_portfolio GROUP BY 1 ORDER BY 1;"
  ```

## Security / deployment

Local development only. Services bind to `127.0.0.1`; do **not** expose the API,
Postgres, or n8n publicly without authentication, TLS, and access controls.
Never commit `.env`, actual credentials, confidential records, or exports
containing secrets. Consider pinning and updating image versions for deployments.

## Next steps

- Send actual Slack/email alerts, with opt-in credentials and deduplication.
- Add Great Expectations or comprehensive schema validation.
- Add an AI explanation step **after** deterministic checks; constrain it to
  supplied facts and validate the output schema.
- Build a Streamlit quality-trends dashboard and CI pipeline.
