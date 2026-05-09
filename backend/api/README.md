# TKNT Pipeline API

## Run
```bash
uvicorn api.main:app --reload --port 8000
```

## Sample requests
```bash
curl -s "http://localhost:8000/" | jq
curl -s "http://localhost:8000/inventory/items?tenant_id=demo_tenant" | jq
curl -s "http://localhost:8000/inventory/types?tenant_id=demo_tenant" | jq

curl -s -X POST "http://localhost:8000/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo_user","input_payload":{"user_input":{"description":"Arrange a neat bedroom.","room_type":"bedroom","floor_area_m2":20,"height":2400,"shape_points":[{"x":0,"y":0},{"x":2400,"y":0},{"x":2400,"y":3500},{"x":0,"y":3500}],"windows":1,"window_direction":"SE","style":"minimal"}}}' | jq
```
