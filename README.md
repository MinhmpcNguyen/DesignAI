# TKNT Normalize-Run API

This repository is trimmed to the code path required by `POST /pipeline/normalize-run`.

The endpoint accepts frontend room geometry, normalizes it into the internal pipeline coordinate system, runs the layout pipeline in the background, enriches selected furniture with catalog model URLs, and restores object positions back into the original frontend coordinate space.

## Run Locally

```bash
cd backend
cp .env.example .env
# edit .env and set OPENAI_API_KEY or one enabled provider key
uv sync
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
```

API base URL:

```text
http://localhost:8000
```

Interactive docs:

```text
http://localhost:8000/docs
```

Docker still works and also installs with `uv`:

```bash
cd backend
docker compose up --build
```

Quality checks:

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```

## Endpoint

Health:

```bash
curl http://localhost:8000/
```

Start a normalize-run job:

```bash
curl -X POST http://localhost:8000/pipeline/normalize-run \
  -H "Content-Type: application/json" \
  -d '{
    "room": {
      "key": "room_1",
      "name": "Bedroom",
      "polygons": [[0, 0], [4.2, 0], [4.2, 3.6], [0, 3.6]],
      "description": "Modern bedroom with clear circulation."
    },
    "walls": [],
    "openings": [],
    "source_unit": "m",
    "tenant_id": "demo_tenant",
    "user_id": "demo_user",
    "style": "modern",
    "allow_generated_accessories": false
  }'
```

Start response:

```json
{
  "id": "demo_user_20260515T083000Z_a1b2c3d4e5f6",
  "status": "queued",
  "statusUrl": "/pipeline/normalize-run/demo_user_20260515T083000Z_a1b2c3d4e5f6/status",
  "resultUrl": "/pipeline/normalize-run/demo_user_20260515T083000Z_a1b2c3d4e5f6/result"
}
```

Poll status:

```bash
curl http://localhost:8000/pipeline/normalize-run/demo_user_20260515T083000Z_a1b2c3d4e5f6/status
```

Status response:

```json
{
  "id": "demo_user_20260515T083000Z_a1b2c3d4e5f6",
  "status": "running",
  "stage": "solver",
  "message": "Solving layout concepts 2/5.",
  "progressCurrent": 2,
  "progressTotal": 5,
  "createdAtUtc": "2026-05-15T08:30:00+00:00",
  "updatedAtUtc": "2026-05-15T08:31:00+00:00",
  "caseIds": ["demo_user_20260515T083000Z_a1b2c3d4e5f6_01_room_1"],
  "currentCaseId": "demo_user_20260515T083000Z_a1b2c3d4e5f6_01_room_1",
  "error": null,
  "statusUrl": "/pipeline/normalize-run/demo_user_20260515T083000Z_a1b2c3d4e5f6/status",
  "resultUrl": "/pipeline/normalize-run/demo_user_20260515T083000Z_a1b2c3d4e5f6/result"
}
```

When status is `ready`, fetch the final frontend payload:

```bash
curl http://localhost:8000/pipeline/normalize-run/demo_user_20260515T083000Z_a1b2c3d4e5f6/result
```

Result response shape:

```json
{
  "objects": [],
  "openings": [],
  "selectedOptionId": "variant_1",
  "options": [],
  "selectionSummary": null
}
```

## Runtime Notes

The API still needs Postgres for runtime inventory and knowledge tables. Docker Compose starts Postgres and the API together.

Catalog assets are loaded from the external catalog API configured by:

```dotenv
TKNT_CATALOG_API_BASE_URL=https://auto-furniture-api2.a-star.group
TKNT_CATALOG_ASSET_BASE_URL=https://storage.mazig.io
```

Set exactly one text LLM provider in `app-config.yaml` and `.env`. OpenAI is enabled by default.
