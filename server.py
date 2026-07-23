# server.py
import http.server
import socketserver
import json
import urllib.parse
import sys
import traceback
import os
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

# Add workspace directory to python path
sys.path.append(str(Path(__file__).parent))

from src.predictor import predict_race_winner
from src.features import get_calendar

ROOT_DIR = Path(__file__).parent
PORT = int(os.environ.get("PORT", "8000"))

class F1DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Disable caching for APIs so developments reflect instantly
        if self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # ── API: Get Races List ─────────────────────────────
        if path == "/api/races":
            try:
                year = int(query.get("year", [2026])[0]) # Default to current year 2026
                races = get_calendar(year)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(races).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }).encode("utf-8"))
            return

        # ── API: Predict Winner ─────────────────────────────
        elif path == "/api/predict":
            try:
                year = int(query.get("year", [2026])[0])
                round_num = int(query.get("round", [1])[0])
                
                # Check for custom grid positions in query
                custom_grid = None
                grid_json = query.get("grid", [None])[0]
                if grid_json:
                    custom_grid = json.loads(grid_json)
                
                predictions = predict_race_winner(year, round_num, custom_grid=custom_grid)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "round": round_num,
                    "predictions": predictions
                }).encode("utf-8"))
                
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }).encode("utf-8"))
            return

        # ── API: Generate Interactive Plotly Charts ──────────
        elif path == "/api/generate_charts":
            try:
                year = int(query.get("year", [2026])[0])
                round_num = int(query.get("round", [1])[0])

                # Run visualization script dynamically
                from src.data_loader import load_session, get_lap_data, get_race_results, get_tyre_strategy
                from src.visualise import (
                    plot_lap_times, plot_tyre_strategy, plot_position_changes,
                    plot_tyre_degradation, plot_team_pace, plot_race_dashboard
                )

                calendar = get_calendar(year)
                matching = [r for r in calendar if r["round"] == round_num]
                if not matching:
                    raise ValueError(f"Round {round_num} not found in schedule for year {year}")
                
                gp_name = matching[0]["name"]
                
                # Load session (instantly uses cache if downloaded)
                session = load_session(year, gp_name, "R")
                laps = get_lap_data(session)
                results = get_race_results(session)
                strategy = get_tyre_strategy(session)

                suffix = f"— {year} {gp_name} GP"

                # Generate Plotly charts (saved as HTML in data/charts)
                plot_lap_times(laps, title_suffix=suffix)
                plot_tyre_strategy(strategy, laps, title_suffix=suffix)
                plot_position_changes(results, title_suffix=suffix)

                top3_drivers = results["Abbreviation"].head(3).tolist()
                plot_tyre_degradation(laps, drivers=top3_drivers, title_suffix=suffix)
                plot_team_pace(laps, title_suffix=suffix)
                plot_race_dashboard(laps, results, strategy, title_suffix=suffix)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "message": f"Charts successfully generated for {year} {gp_name} GP!",
                    "gp_name": gp_name
                }).encode("utf-8"))

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }).encode("utf-8"))
            return
        
        # ── API: Live Backend Status ─────────────────────────
        elif path == "/api/live_status":
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "server_time_utc": datetime.now(timezone.utc).isoformat(),
                    "refresh_hint_seconds": 30
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }).encode("utf-8"))
            return

        # ── Serve Standard Static Files ──────────────────────
        else:
            super().do_GET()

# Run the web server
if __name__ == "__main__":
    handler = partial(F1DashboardHandler, directory=str(ROOT_DIR))
    
    # Enable socket re-use to prevent "Address already in use" errors during quick restarts
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    
    with socketserver.ThreadingTCPServer(("", PORT), handler) as httpd:
        print("\n" + "="*50)
        print(f"  F1 AI PREDICTOR SERVER RUNNING")
        print(f"  URL: http://localhost:{PORT}")
        print("  Press Ctrl+C to stop the server")
        print("="*50 + "\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
