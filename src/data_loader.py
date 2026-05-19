# src/data_loader.py
# ─────────────────────────────────────────────
# What this file does:
#   - Connects to FastF1 to pull real F1 session data
#   - Caches data locally so you don't re-download every run
#   - Returns clean DataFrames for laps, telemetry, results
# ─────────────────────────────────────────────

import fastf1
import pandas as pd
import numpy as np
from pathlib import Path
from rich.console import Console
from rich.progress import track

console = Console()

# ── Cache setup ───────────────────────────────
# FastF1 stores downloaded data in a local folder.
# Without cache, every run re-downloads ~50MB per session.
CACHE_DIR = Path("data/fastf1_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


def load_session(year: int, grand_prix: str, session_type: str = "R"):
    """
    Load a session from FastF1.

    Args:
        year        : e.g. 2024
        grand_prix  : e.g. "Bahrain", "Monaco", "British"
        session_type: "R" = Race, "Q" = Qualifying, "FP1/FP2/FP3"

    Returns:
        fastf1.Session object (fully loaded)
    """
    console.print(f"\n[bold cyan]Loading:[/] {year} {grand_prix} GP — {session_type}")
    console.print("[dim]First load downloads data (~30s). Subsequent loads use cache (instant).[/dim]")

    session = fastf1.get_session(year, grand_prix, session_type)
    session.load()  # downloads: laps, telemetry, weather, car data

    console.print(f"[bold green]✓ Loaded![/] {len(session.laps)} laps across {session.laps['Driver'].nunique()} drivers")
    return session


def get_lap_data(session) -> pd.DataFrame:
    """
    Extract clean lap-by-lap data from a session.

    Each row = one lap by one driver.
    Columns include: lap time, sector times, tyre compound,
    tyre age, pit stops, speed trap, position.
    """
    laps = session.laps.copy()

    # Convert lap time from timedelta to seconds (easier for ML later)
    laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()
    laps["Sector1Seconds"] = laps["Sector1Time"].dt.total_seconds()
    laps["Sector2Seconds"] = laps["Sector2Time"].dt.total_seconds()
    laps["Sector3Seconds"] = laps["Sector3Time"].dt.total_seconds()

    # Keep only useful columns
    cols = [
        "Driver", "DriverNumber", "Team",
        "LapNumber", "LapTimeSeconds",
        "Sector1Seconds", "Sector2Seconds", "Sector3Seconds",
        "Compound", "TyreLife",
        "FreshTyre", "PitInTime", "PitOutTime",
        "SpeedI1", "SpeedI2", "SpeedFL", "SpeedST",
        "Position", "IsPersonalBest"
    ]
    # Only keep columns that exist in this session
    cols = [c for c in cols if c in laps.columns]
    laps = laps[cols].copy()

    # Drop laps with no recorded time (in-laps, out-laps, safety car)
    laps = laps.dropna(subset=["LapTimeSeconds"])

    # Flag pit laps
    laps["IsPitLap"] = laps["PitInTime"].notna() | laps["PitOutTime"].notna()

    console.print(f"[dim]Lap data: {len(laps)} clean laps extracted[/dim]")
    return laps.reset_index(drop=True)


def get_driver_telemetry(session, driver: str, lap_number: int = None):
    """
    Get raw telemetry (speed, throttle, brake, gear, DRS)
    for a specific driver — either their fastest lap or a specific lap.

    Args:
        session    : loaded FastF1 session
        driver     : 3-letter code e.g. "VER", "HAM", "NOR"
        lap_number : specific lap (None = fastest lap)

    Returns:
        DataFrame with columns: Time, Speed, Throttle, Brake, Gear, DRS, X, Y
    """
    if lap_number is None:
        lap = session.laps.pick_driver(driver).pick_fastest()
        console.print(f"[dim]Telemetry: {driver} fastest lap[/dim]")
    else:
        lap = session.laps.pick_driver(driver).iloc[lap_number - 1]
        console.print(f"[dim]Telemetry: {driver} lap {lap_number}[/dim]")

    tel = lap.get_telemetry()

    # Add distance from start (useful for track position plots)
    tel["DistanceFromStart"] = tel["Distance"]

    return tel


def get_race_results(session) -> pd.DataFrame:
    """
    Get the final race results with finishing position,
    points, fastest lap, and gap to winner.
    """
    results = session.results.copy()

    # Print available columns so we can see what FastF1 3.8 gives us
    console.print(f"[dim]Available result columns: {list(results.columns)}[/dim]")

    # Flexible column selection — only grab what exists
    desired = [
        "DriverNumber", "Abbreviation", "FullName",
        "TeamName", "Position", "Points",
        "GridPosition", "Status", "Time"
    ]
    cols = [c for c in desired if c in results.columns]
    results = results[cols].copy()

    results["Position"] = pd.to_numeric(results["Position"], errors="coerce")
    results["GridPosition"] = pd.to_numeric(results["GridPosition"], errors="coerce")

    if "GridPosition" in results.columns and "Position" in results.columns:
        results["PositionsGained"] = results["GridPosition"] - results["Position"]

    console.print(f"[dim]Results: {len(results)} drivers[/dim]")
    return results.reset_index(drop=True)

def get_tyre_strategy(session) -> pd.DataFrame:
    """
    Build a tyre strategy summary per driver:
    which compounds they used, how many laps on each,
    and how many pit stops they made.
    """
    laps = get_lap_data(session)

    strategy = []
    for driver in laps["Driver"].unique():
        driver_laps = laps[laps["Driver"] == driver].copy()

        # Count stints (each compound change = new stint)
        stints = driver_laps.groupby(
            (driver_laps["Compound"] != driver_laps["Compound"].shift()).cumsum()
        ).agg(
            Compound=("Compound", "first"),
            Laps=("LapNumber", "count"),
            AvgLapTime=("LapTimeSeconds", "mean")
        ).reset_index(drop=True)

        pit_stops = int(driver_laps["IsPitLap"].sum() / 2)  # in+out = 1 stop

        strategy.append({
            "Driver": driver,
            "TotalStints": len(stints),
            "PitStops": pit_stops,
            "Compounds": " → ".join(stints["Compound"].tolist()),
            "StintLaps": stints["Laps"].tolist(),
        })

    df = pd.DataFrame(strategy)
    console.print(f"[dim]Strategy: {len(df)} drivers analysed[/dim]")
    return df


def get_weather(session) -> pd.DataFrame:
    """
    Get weather data across the session:
    air temp, track temp, humidity, wind speed, rainfall.
    """
    weather = session.weather_data.copy()
    console.print(f"[dim]Weather: {len(weather)} data points[/dim]")
    return weather