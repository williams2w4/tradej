# Trade Journal Platform

A full-stack trade journal management system featuring a React + Vite frontend and a FastAPI backend backed by PostgreSQL. The application supports uploading IBKR trade data, calculating performance metrics, browsing trades, and visualising activity on a calendar.

## Features

- Unified filters (asset code, type, direction, date range presets) shared across dashboard and trade views.
- Dashboard with win rate, total/average PnL, profit factor, and asset-level breakdown.
- Trade log with expandable child trades, Pine Script export, and bulk deletion.
- Calendar visualisation with per-day counts and PnL, with quick drill-down to trades.
- Data import pipeline with validation for IBKR CSV files and automatic parent-trade aggregation.
- Timezone-aware filtering and display, user-configurable from the UI.

## Getting Started

### Local Development (without Docker)

1. **Backend**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/tradej"
   uvicorn app.main:app --reload
   ```

2. **Frontend**
   ```bash
   cd frontend
   npm install
   # optional: override the backend API target (defaults to http://localhost:8000)
   # export VITE_PROXY_TARGET="http://localhost:8000"
   npm run dev
   ```

### Docker Compose

```bash
docker-compose up --build
```

The backend will be accessible at `http://localhost:8000`, and the Vite dev server at `http://localhost:5173`.
The frontend container forwards API calls to the backend using the `VITE_PROXY_TARGET`
environment variable, which defaults to `http://localhost:8000` for local development and
is automatically set to `http://backend:8000` inside Docker Compose.

## Testing

Run backend tests with:

```bash
cd backend
pytest
```

Frontend build check:

```bash
cd frontend
npm install
npm run build
```

## Mock Data

A sample IBKR CSV file is available under `mock/TradeNote.csv` for testing the import pipeline.
