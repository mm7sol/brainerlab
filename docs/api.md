# API

Base: `/api`. Interactive docs: `/docs`, `/openapi.json`. Pagination: `limit` (default 50,
max 500), `offset`. Errors: `{detail}` with 4xx codes.

```
GET /api/species
GET /api/datasets[?species=]
GET /api/datasets/{id}
GET /api/neurons?dataset_id=&q=&type=&region=&limit=&offset=
GET /api/neurons/{id}?dataset_id=
GET /api/connections?dataset_id=&source=&target=&kind=(chemical|electrical|all)&limit=&offset=
GET /api/graph/subgraph?dataset_id=&seeds=A,B&depth=1&direction=(in|out|both)&kind=all
GET /api/graph/stats?dataset_id=
GET /api/experiments[?limit=&offset=]
POST /api/experiments        {species,dataset_id,model,parameters,duration_ms,seed,
                              stimulus[],manipulations{...},research_question?}
GET /api/experiments/{id}
POST /api/simulations        {experiment_id} → runs normal + modified, stores results
GET /api/results/{experiment_id}
GET /api/reports/{experiment_id}
GET /api/provenance/{experiment_id}   # dataset→version→source→publication→
                                      # transformation→simulation→result chain
POST /api/ai/explain         {question, dataset_id?, neuron_id?, experiment_id?}
GET /api/export/{id}.json | /api/export/{id}.csv
GET /experiment/{id}         # human page (HTML)
```

`POST /api/experiments` validates: known dataset, known model, known parameters, known
neuron/edge IDs; unknown names → 422 (never silently ignored). `dataset_id` and
experiment IDs double as store filenames: only plain slugs
(`[A-Za-z0-9_-]`, ≤121 chars) are accepted — anything else → 422 before any
store access (path traversal rejected, see `tests/test_all.py::TestSecurity`).
Auth (M10): roles
visitor/researcher/admin; V1 accepts optional `X-Role` header, POSTs need researcher+.
