# src/export_data.py
# ─────────────────────────────────────────────────────────
# WHAT THIS DOES:
#   Loops through all 24 rounds of 2024 F1 season.
#   For each round pulls: Race + Qualifying data.
#   Saves everything into data/f1_data.json
#   That JSON file is what our HTML dashboard reads.
#
# WHY JSON:
#   HTML/JavaScript can read JSON directly.
#   Python can't run inside a browser.
#   JSON is the bridge between Python and your dashboard.
#
# HOW LONG IT TAKES:
#   First run: 20-40 mins (downloads 24 races from FastF1)
#   Every run after: ~2 mins (reads from local cache)
# ─────────────────────────────────────────────────────────

import fastf1
import pandas as pd
import json
import math
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

# ── Setup cache ──────────────────────────────────────────
# FastF1 stores downloaded data locally so we don't
# re-download on every run. Cache lives in data/fastf1_cache/
CACHE_DIR = Path("data/fastf1_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

# ── Output file ──────────────────────────────────────────
# This is the file our HTML dashboard will read
OUTPUT_FILE = Path("data/f1_data.json")

# ── All 24 rounds of 2024 season ─────────────────────────
# Format: (round_number, name, country, flag_emoji, circuit_name)
RACES_2024 = [
    (1,  "Bahrain",         "Bahrain",      "🇧🇭", "Bahrain International Circuit"),
    (2,  "Saudi Arabia",    "Saudi Arabia", "🇸🇦", "Jeddah Corniche Circuit"),
    (3,  "Australia",       "Australia",    "🇦🇺", "Albert Park Circuit"),
    (4,  "Japan",           "Japan",        "🇯🇵", "Suzuka International Racing Course"),
    (5,  "China",           "China",        "🇨🇳", "Shanghai International Circuit"),
    (6,  "Miami",           "USA",          "🇺🇸", "Miami International Autodrome"),
    (7,  "Emilia Romagna",  "Italy",        "🇮🇹", "Autodromo Enzo e Dino Ferrari"),
    (8,  "Monaco",          "Monaco",       "🇲🇨", "Circuit de Monaco"),
    (9,  "Canada",          "Canada",       "🇨🇦", "Circuit Gilles Villeneuve"),
    (10, "Spain",           "Spain",        "🇪🇸", "Circuit de Barcelona-Catalunya"),
    (11, "Austria",         "Austria",      "🇦🇹", "Red Bull Ring"),
    (12, "British",         "UK",           "🇬🇧", "Silverstone Circuit"),
    (13, "Hungarian",       "Hungary",      "🇭🇺", "Hungaroring"),
    (14, "Belgian",         "Belgium",      "🇧🇪", "Circuit de Spa-Francorchamps"),
    (15, "Dutch",           "Netherlands",  "🇳🇱", "Circuit Zandvoort"),
    (16, "Italian",         "Italy",        "🇮🇹", "Autodromo Nazionale Monza"),
    (17, "Azerbaijan",      "Azerbaijan",   "🇦🇿", "Baku City Circuit"),
    (18, "Singapore",       "Singapore",    "🇸🇬", "Marina Bay Street Circuit"),
    (19, "US",              "USA",          "🇺🇸", "Circuit of the Americas"),
    (20, "Mexico City",     "Mexico",       "🇲🇽", "Autodromo Hermanos Rodriguez"),
    (21, "São Paulo",       "Brazil",       "🇧🇷", "Autodromo Jose Carlos Pace"),
    (22, "Las Vegas",       "USA",          "🇺🇸", "Las Vegas Strip Circuit"),
    (23, "Qatar",           "Qatar",        "🇶🇦", "Lusail International Circuit"),
    (24, "Abu Dhabi",       "UAE",          "🇦🇪", "Yas Marina Circuit"),
]

# ── Team colours (official 2024) ─────────────────────────
TEAM_COLORS = {
    "Red Bull Racing": "#3671C6",
    "Ferrari":         "#E8002D",
    "Mercedes":        "#27F4D2",
    "McLaren":         "#FF8000",
    "Aston Martin":    "#229971",
    "Alpine":          "#FF87BC",
    "Williams":        "#64C4FF",
    "RB":              "#6692FF",
    "Kick Sauber":     "#52E252",
    "Haas F1 Team":    "#B6BABD",
}


def safe_float(val):
    """Convert a value to float, return None if not possible."""
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else round(f, 3)
    except:
        return None


def safe_str(val):
    """Convert to string safely."""
    try:
        if pd.isna(val):
            return None
        return str(val)
    except:
        return str(val) if val is not None else None


def extract_race_data(session, round_num, race_info):
    """
    Pull all useful data from a race session.
    Returns a dictionary with everything the dashboard needs.
    """
    rnd, name, country, flag, circuit = race_info

    # ── Lap data ─────────────────────────────────────────
    # Every lap by every driver: time, compound, tyre age, position
    laps = session.laps.copy()
    laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()

    lap_rows = []
    for _, lap in laps.iterrows():
        lap_time = safe_float(lap.get("LapTimeSeconds"))
        if lap_time is None or lap_time > 300:  # skip outliers
            continue
        lap_rows.append({
            "driver":    safe_str(lap.get("Driver")),
            "lap":       int(lap.get("LapNumber", 0)),
            "time":      lap_time,
            "compound":  safe_str(lap.get("Compound")),
            "tyreAge":   safe_float(lap.get("TyreLife")),
            "position":  safe_float(lap.get("Position")),
            "pitIn":     lap.get("PitInTime") is not pd.NaT and pd.notna(lap.get("PitInTime")),
            "pitOut":    lap.get("PitOutTime") is not pd.NaT and pd.notna(lap.get("PitOutTime")),
            "speedST":   safe_float(lap.get("SpeedST")),
            "speedFL":   safe_float(lap.get("SpeedFL")),
            "s1":        safe_float(lap.get("Sector1Time") and lap.get("Sector1Time").total_seconds() if pd.notna(lap.get("Sector1Time")) else None),
            "s2":        safe_float(lap.get("Sector2Time") and lap.get("Sector2Time").total_seconds() if pd.notna(lap.get("Sector2Time")) else None),
            "s3":        safe_float(lap.get("Sector3Time") and lap.get("Sector3Time").total_seconds() if pd.notna(lap.get("Sector3Time")) else None),
        })

    # ── Race results ─────────────────────────────────────
    # Final finishing order, points, grid position
    results = session.results.copy()
    result_rows = []
    for _, r in results.iterrows():
        result_rows.append({
            "driver":      safe_str(r.get("Abbreviation")),
            "fullName":    safe_str(r.get("FullName")),
            "team":        safe_str(r.get("TeamName")),
            "teamColor":   TEAM_COLORS.get(safe_str(r.get("TeamName")), "#888888"),
            "position":    safe_float(r.get("Position")),
            "gridPos":     safe_float(r.get("GridPosition")),
            "points":      safe_float(r.get("Points")),
            "status":      safe_str(r.get("Status")),
        })

    # ── Tyre strategy ────────────────────────────────────
    # Per driver: which compounds, how many laps each stint
    strategy = []
    for driver in laps["Driver"].unique():
        dlaps = laps[laps["Driver"] == driver].copy()
        dlaps = dlaps.dropna(subset=["LapTimeSeconds"])

        stints = []
        prev_compound = None
        stint_start = 1
        stint_laps = 0

        for _, lap in dlaps.sort_values("LapNumber").iterrows():
            compound = safe_str(lap.get("Compound"))
            if compound != prev_compound and prev_compound is not None:
                stints.append({
                    "compound": prev_compound,
                    "laps": stint_laps,
                    "lapStart": stint_start
                })
                stint_start += stint_laps
                stint_laps = 0
            prev_compound = compound
            stint_laps += 1

        if prev_compound:
            stints.append({
                "compound": prev_compound,
                "laps": stint_laps,
                "lapStart": stint_start
            })

        strategy.append({
            "driver": safe_str(driver),
            "stints": stints,
            "pitStops": len(stints) - 1
        })

    # ── Weather summary ──────────────────────────────────
    weather = {}
    try:
        wx = session.weather_data
        weather = {
            "airTemp":    round(float(wx["AirTemp"].mean()), 1),
            "trackTemp":  round(float(wx["TrackTemp"].mean()), 1),
            "humidity":   round(float(wx["Humidity"].mean()), 1),
            "windSpeed":  round(float(wx["WindSpeed"].mean()), 2),
            "rainfall":   bool(wx["Rainfall"].any()),
        }
    except:
        weather = {"airTemp": 0, "trackTemp": 0, "humidity": 0, "windSpeed": 0, "rainfall": False}

    # ── Pit stop timeline ────────────────────────────────
    pit_stops = []
    for _, lap in laps[laps["PitInTime"].notna()].iterrows():
        pit_stops.append({
            "driver":  safe_str(lap.get("Driver")),
            "lap":     int(lap.get("LapNumber", 0)),
            "compound": safe_str(lap.get("Compound")),
        })

    # ── Speed trap data ──────────────────────────────────
    speed_data = []
    for driver in laps["Driver"].unique():
        dlaps = laps[laps["Driver"] == driver]
        speeds = dlaps["SpeedST"].dropna()
        if len(speeds) > 0:
            speed_data.append({
                "driver":   safe_str(driver),
                "maxSpeed": safe_float(speeds.max()),
                "avgSpeed": safe_float(speeds.mean()),
            })
    speed_data.sort(key=lambda x: x["maxSpeed"] or 0, reverse=True)

    total_laps = int(laps["LapNumber"].max()) if len(laps) > 0 else 0

    return {
        "round":      rnd,
        "name":       name,
        "country":    country,
        "flag":       flag,
        "circuit":    circuit,
        "totalLaps":  total_laps,
        "weather":    weather,
        "laps":       lap_rows,
        "results":    result_rows,
        "strategy":   strategy,
        "pitStops":   pit_stops,
        "speedTrap":  speed_data,
    }


def extract_qualifying_data(session, round_num):
    """
    Pull qualifying data: Q1, Q2, Q3 best lap times per driver.
    """
    laps = session.laps.copy()
    laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()

    quali_rows = []
    for driver in laps["Driver"].unique():
        dlaps = laps[laps["Driver"] == driver]
        row = {"driver": safe_str(driver)}

        for q in ["Q1", "Q2", "Q3"]:
            qlaps = dlaps[dlaps["Compound"].notna()]
            # Get best lap in each session segment
            # FastF1 doesn't split by Q1/Q2/Q3 in laps directly
            # so we use the results table instead
            row[q] = None

        # Get from results which has Q1/Q2/Q3 times
        try:
            results = session.results
            driver_result = results[results["Abbreviation"] == driver]
            if not driver_result.empty:
                r = driver_result.iloc[0]
                for q in ["Q1", "Q2", "Q3"]:
                    if q in r and pd.notna(r[q]):
                        try:
                            row[q] = round(float(r[q].total_seconds()), 3)
                        except:
                            row[q] = None
        except:
            pass

        quali_rows.append(row)

    return quali_rows


# ── MAIN: loop through all races ─────────────────────────
def main():
    console.print("\n[bold red]F1 2024 DATA EXPORTER[/bold red]")
    console.print("[dim]This will download all 24 races. First run takes 20-40 mins.[/dim]")
    console.print("[dim]Subsequent runs use cache and take ~2 mins.[/dim]\n")

    all_data = {
        "season": 2024,
        "races": [],
        "qualifying": [],
        "exported_at": str(pd.Timestamp.now()),
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console
    ) as progress:

        race_task = progress.add_task("[cyan]Pulling races...", total=len(RACES_2024))

        for race_info in RACES_2024:
            rnd, name, country, flag, circuit = race_info

            # ── Pull Race ─────────────────────────────────
            progress.update(race_task, description=f"[cyan]Race: {name} (Round {rnd})")
            try:
                race_session = fastf1.get_session(2024, rnd, "R")
                race_session.load(telemetry=False, weather=True, messages=False)
                race_data = extract_race_data(race_session, rnd, race_info)
                all_data["races"].append(race_data)
                console.print(f"  [green]✓[/green] Race {rnd}: {name} — {len(race_data['laps'])} laps")
            except Exception as e:
                console.print(f"  [red]✗[/red] Race {rnd}: {name} — {e}")
                all_data["races"].append({
                    "round": rnd, "name": name, "country": country,
                    "flag": flag, "circuit": circuit,
                    "error": str(e), "laps": [], "results": []
                })

            # ── Pull Qualifying ───────────────────────────
            progress.update(race_task, description=f"[yellow]Quali: {name} (Round {rnd})")
            try:
                quali_session = fastf1.get_session(2024, rnd, "Q")
                quali_session.load(telemetry=False, weather=False, messages=False)
                quali_data = extract_qualifying_data(quali_session, rnd)
                all_data["qualifying"].append({
                    "round": rnd,
                    "name": name,
                    "drivers": quali_data
                })
                console.print(f"  [green]✓[/green] Quali {rnd}: {name} — {len(quali_data)} drivers")
            except Exception as e:
                console.print(f"  [yellow]~[/yellow] Quali {rnd}: {name} — {e}")
                all_data["qualifying"].append({
                    "round": rnd, "name": name, "drivers": []
                })

            progress.advance(race_task)

    # ── Save to JSON ──────────────────────────────────────
    console.print("\n[bold cyan]Saving to data/f1_data.json...[/bold cyan]")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)

    size_mb = OUTPUT_FILE.stat().st_size / 1024 / 1024
    console.print(f"[bold green]✓ Done! Saved {size_mb:.1f} MB to {OUTPUT_FILE}[/bold green]")
    console.print(f"[dim]Races: {len(all_data['races'])} · Qualifying: {len(all_data['qualifying'])}[/dim]")
    console.print("\n[bold]Now open f1_dashboard.html in your browser to see all races![/bold]")


if __name__ == "__main__":
    main()