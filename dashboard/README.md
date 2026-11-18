# DataGuard Streamlit dashboard (free, local)

Adds an interactive read-only dashboard to the existing DataGuard Compose project.
This add-on **does not modify PostgreSQL data, n8n workflows or `.env`**.

## Install in your existing project

Copy `dashboard/` and `docker-compose.dashboard.yml` into the directory that already contains `docker-compose.yml`.
Do **not** replace your existing project folder or delete volumes.

From Terminal, inside `dataguard-ai-n8n/`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dashboard.yml up -d --build dashboard
docker compose -f docker-compose.yml -f docker-compose.dashboard.yml ps
```

Open http://localhost:8501 in a browser. The dashboard gets audit data through your existing FastAPI service `http://api:8000/runs` and `/alerts` on the private Docker network.

If you haven't run any validations yet, run the existing n8n workflow, or execute:

```bash
curl -X POST http://localhost:8000/validate -H 'Content-Type: application/json' -d '{}'
```

Then click **Refresh data** in Streamlit. Do **not** rerun the seed command: it resets the audit history.

To inspect dashboard errors:

```bash
docker compose -f docker-compose.yml -f docker-compose.dashboard.yml logs --tail=60 dashboard
```

To stop only the dashboard:

```bash
docker compose -f docker-compose.yml -f docker-compose.dashboard.yml stop dashboard
```

The API returns a maximum of 100 recent validation runs/alerts. Charts reflect only that window, and repeated executions for the same snapshot date will count separately. This is a starter dashboard, not an enterprise analytics warehouse.
