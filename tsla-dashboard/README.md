# TSLA Dashboard (Vite + React)

This project is a small TSLA dashboard built with Vite + React. It polls a local Flask API at `http://localhost:5000/api/tsla` every second and displays:

- Current TSLA price in large text
- Day high / low
- Volume
- A live line chart of recent price history using TradingView Lightweight Charts (`lightweight-charts`)

The Flask endpoint is implemented in `tsla_api.py` at the workspace root and proxies Alpha Vantage&apos;s `GLOBAL_QUOTE` for TSLA.

## Getting started

### 1. Start the TSLA API

From the workspace root (where `tsla_api.py` lives):

```bash
python tsla_api.py
```

This will start a Flask server on `http://localhost:5000` with the `/api/tsla` endpoint.

### 2. Start the React dev server

From the `tsla-dashboard` directory:

```bash
cd tsla-dashboard
npm install        # if you haven&apos;t already run this
npm run dev
```

Then open the printed localhost URL in your browser (by default `http://localhost:5173`).

## Notes

- The dashboard polls the API every second and appends prices to an in-memory history used for the chart.
- If the API is down or returns an error, the UI shows a &quot;Disconnected&quot; status with the error message.
- You can customize styling and layout via `src/App.css` and `src/index.css`.

