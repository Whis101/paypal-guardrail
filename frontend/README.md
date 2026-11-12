# Guardrail frontend

React + TypeScript + Vite UI for Guardrail (spending limits for AI shopping agents). Transactions grid uses AG Grid Community.

## Run locally

```bash
npm install
npm run dev   # needs the FastAPI backend running on http://localhost:8000
```

Open http://localhost:5173. The dev server proxies `/api/*` to `http://localhost:8000`, so no CORS setup is needed.
To point at a different backend, set `VITE_API_BASE_URL` (e.g. `VITE_API_BASE_URL=https://api.example.com npm run dev`).

## Checks

```bash
npm run build   # tsc + vite build
npm run lint    # oxlint
```
