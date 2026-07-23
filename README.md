# F1 AI Predictor Dashboard

Interactive Formula 1 dashboard built with Python + FastF1 for data, a custom ML predictor for simulation, and a modern web UI for live comparison and race analytics charts.

## What this project does

1. Pulls F1 race/qualifying history from FastF1 (with local cache).
2. Builds driver/team trend features from historical races.
3. Trains a Random Forest model to estimate expected finish and win probability.
4. Lets you edit starting grid positions and compare baseline vs edited outcomes.
5. Generates Plotly analytics charts (lap pace, strategy, tyre degradation, team pace, dashboard).

## How the app is structured

- `server.py`: single Python web server for APIs + static frontend hosting.
- `index.html`, `app.js`, `styles.css`: dashboard UI, live updates, and comparison graph.
- `src/predictor.py`: ML prediction pipeline.
- `src/features.py`: schedule + feature engineering + cached race results.
- `src/data_loader.py`: FastF1 session loading and clean lap/results extraction.
- `src/visualise.py`: Plotly chart generation to `data/charts/*.html`.

## Local setup

```bash
python -m venv venv
# Windows PowerShell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the website

```bash
python server.py
```

Then open:

`http://localhost:8000`

Notes:
- First-time data pulls can take ~30s per race session.
- Later runs are much faster due to `data/fastf1_cache/`.
- Charts are generated dynamically into `data/charts/`.

## Real-time behavior in UI

- Live backend heartbeat (`/api/live_status`) updates the status indicator.
- Race metadata refreshes every 30 seconds.
- Grid order edits auto-trigger simulation updates (debounced).
- Comparison graph shows **Baseline vs Current** win probabilities.

## Deploy (Render example)

1. Push this repo to GitHub.
2. In Render, create a **Web Service** from this repo.
3. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python server.py`
4. Render will provide `PORT`; `server.py` reads it automatically.
5. Open the generated Render URL to access the live website.

## Requirements

- Python 3.11+
- Internet access for FastF1 data fetches

## License

MIT
