# Architecture notes

## Boundaries

The system is split into orchestration (n8n), validation (Python/FastAPI), and
persistence (PostgreSQL). The n8n and app data use distinct databases but share
a Postgres server to keep local setup simple.

## Data flow

1. Seed script writes dated synthetic portfolio snapshots.
2. Manual or scheduled n8n trigger calls POST `/validate` with `{}`.
3. API locates latest snapshot, fetches previous-day aggregate, executes checks.
4. API writes validation run to SQL and returns findings.
5. n8n routes `issues_found` into POST `/alerts`; the endpoint logs the alert.
6. Both GET endpoints provide auditable local output.

## Limitations

- No external notifications or LLM integration in MVP.
- Repeated validations create separate runs; alerts are unique per run.
- Per-record exceptions are not yet stored separately.
- SQL data is recreated by seed and must not include proprietary datasets.
- Demo thresholds are not institution-specific risk policy.
