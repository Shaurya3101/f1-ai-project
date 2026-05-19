# F1 AI Project

Python toolkit for pulling Formula 1 session data with [FastF1](https://github.com/theOehrly/Fast-F1) and building interactive race visualizations with Plotly.

## Features

- Load race, qualifying, or practice sessions by year and Grand Prix
- Lap times, tyre strategy, position changes, degradation, and team pace charts
- Combined race dashboard (single HTML report)
- Optional full-season JSON export for a web dashboard (`src/export_data.py`)

## Setup

```bash
python -m venv venv
# Windows PowerShell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

The first run downloads session data (~30 seconds per session). Later runs use the local cache in `data/fastf1_cache/`.

Charts are saved to `data/charts/` as `.html` files — open them in any browser.

## Project structure

```
f1-ai-project/
├── main.py              # Example: 2024 Bahrain GP charts
├── src/
│   ├── data_loader.py   # FastF1 session loading
│   ├── visualise.py     # Plotly charts
│   └── export_data.py   # Full-season JSON export
├── data/
│   ├── fastf1_cache/    # Auto-created (gitignored)
│   └── charts/          # Generated HTML (gitignored)
└── requirements.txt
```

## Requirements

- Python 3.11+
- Internet on first run (FastF1 API)

## License

MIT
