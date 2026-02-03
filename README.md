# ADA Clinical Reasoning Engine

A SaaS-ready clinical decision support service that evaluates patient records against ADA 2026 diabetes guidelines and payer/clinic rules.

## Quick Start (local)

```bash
docker compose build
docker compose up
```

Open `http://localhost:8000/docs` and use header `X-API-Key: demo-key`.

## Render Deployment

This repo includes a `render.yaml` Blueprint. On Render:

1. **Create a new Blueprint** and point it at this repository.
2. Render will build a web service and set the required environment variables.
3. Your service will start with `uvicorn` and bind to `$PORT` automatically.

### Required environment variables

- `API_KEY` - API key required to access `/evaluate`.
- `CONFIG_DIR` - optional path to tenant configs (defaults to `./configs/tenants`).
- `ONTOLOGY_DIR` - optional path to ontology files (defaults to `./ontologies`).

### Example request

```bash
curl -X POST "$RENDER_EXTERNAL_URL/evaluate" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Tenant-Id: clinic_001" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "T001",
    "age": 58,
    "sex": "M",
    "diagnoses": [{"icd10": "E11.9", "mondo": "MONDO:0005148", "name": "Type 2 Diabetes"}],
    "labs": [{"loinc": "LOINC:4548-4", "value": 9.6, "unit": "%", "date": "2024-01-01"}],
    "medications": [{"rxnorm_code": "rxnorm:6809", "name": "Metformin", "start_date": "2023-01-01"}],
    "vital_signs": {"weight_kg": 95, "height_cm": 175, "date": "2024-01-01"},
    "pregnant": false,
    "payer": "medicare"
  }'
```

## Tests

```bash
pytest
```
