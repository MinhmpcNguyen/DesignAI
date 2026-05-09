# TKNT Backend

FastAPI backend package for the current TKNT pipeline, inventory, auth, account, and snapshot image APIs.

## Run With Docker

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY or the provider keys you use
docker compose up --build
```

Runtime inventory, design knowledge, and size profiles are loaded from Postgres. `TKNT_AUTO_LOAD_DEMO_DATA` defaults to `0`; set it to `1` only when you intentionally want to seed the bundled `synthetic_data/inventory.json` into Postgres before serving real requests.

## Switch OpenAI And Azure

Use OpenAI:

```dotenv
OPENAI_AZURE=0
OPENAI_API_KEY=sk-...
OPENAI_PRIMARY_MODEL=gpt-5.4-mini
OPENAI_HELPER_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Use Azure OpenAI:

```dotenv
OPENAI_AZURE=1
AZURE_OPENAI_ENDPOINT=https://<resource-name>.openai.azure.com
AZURE_OPENAI_API_KEY=<azure-key>
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=<chat-deployment-name>
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<embedding-deployment-name>
```

For Azure, the `*_DEPLOYMENT` values are Azure deployment names, not model catalog names. `AZURE_OPENAI_PRIMARY_DEPLOYMENT` and `AZURE_OPENAI_HELPER_DEPLOYMENT` can override the shared chat deployment when needed.

API base URL:

```text
http://localhost:8000
```

Interactive docs:

```text
http://localhost:8000/docs
```

OpenAPI JSON:

```text
http://localhost:8000/openapi.json
```

A static copy is also included at `openapi.json`.

## Main Endpoints

Health:

```bash
curl http://localhost:8000/
```

Pipeline:

```bash
curl -X POST http://localhost:8000/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "input_payload": {
      "user_input": {
        "description": "Arrange a neat bedroom.",
        "room_type": "bedroom",
        "floor_area_m2": 20,
        "height": 2400,
        "shape_points": [
          {"x": 0, "y": 0},
          {"x": 2400, "y": 0},
          {"x": 2400, "y": 3500},
          {"x": 0, "y": 3500}
        ],
        "windows": 1,
        "window_direction": "SE",
        "style": "minimal"
      }
    }
  }'
```

Then poll:

```bash
curl http://localhost:8000/pipeline/{case_id}/status
curl http://localhost:8000/pipeline/{case_id}/result
```

Inventory:

```bash
curl http://localhost:8000/inventory/items
curl http://localhost:8000/inventory/types
curl "http://localhost:8000/inventory/search?q=chair"
```

Auth:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123","display_name":"Demo"}'

curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123"}'
```

Account APIs use bearer auth:

```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <access_token>"
```

## Local CLI

```bash
python run_case_backend_cli.py --input sample_input.json --user demo_user --stdout wrapped
```
