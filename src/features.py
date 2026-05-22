# src/features.py
import fastf1
import pandas as pd
import numpy as np
from pathlib import Path
from rich.console import Console

console = Console()

CIRCUIT_TYPES = {
    "Bahrain": "balanced",
    "Saudi Arabia": "street",
    "Australia": "street",
    "Japan": "high_speed",
    "China": "balanced",
    "Miami": "street",
    "Emilia Romagna": "high_speed",
    "Monaco": "street",
    "Canada": "street",
    "Spain": "balanced",
    "Austria": "high_speed",
    "British": "high_speed",
    "Hungarian": "balanced",
    "Belgian": "high_speed",
    "Dutch": "balanced",
    "Italian": "high_speed",
    "Azerbaijan": "street",
    "Singapore": "street",
    "US": "balanced",
    "United States": "balanced",
    "Mexico City": "balanced",
    "São Paulo": "balanced",
    "Las Vegas": "street",
    "Qatar": "high_speed",
    "Abu Dhabi": "balanced"
}

COUNTRY_FLAGS = {
    "Bahrain": "🇧🇭",
    "Saudi Arabia": "🇸🇦",
    "Australia": "🇦🇺",
    "Japan": "🇯🇵",
    "China": "🇨🇳",
    "Miami": "🇺🇸",
    "Emilia Romagna": "🇮🇹",
    "Monaco": "🇲🇨",
    "Canada": "🇨🇦",
    "Spain": "🇪🇸",
    "Austria": "🇦🇹",
    "British": "🇬🇧",
    "UK": "🇬🇧",
    "Hungarian": "🇭🇺",
    "Hungary": "🇭🇺",
    "Belgian": "🇧🇪",
    "Belgium": "🇧🇪",
    "Dutch": "🇳🇱",
    "Netherlands": "🇳🇱",
    "Italian": "🇮🇹",
    "Italy": "🇮🇹",
    "Azerbaijan": "🇦🇿",
    "Singapore": "🇸🇬",
    "US": "🇺🇸",
    "USA": "🇺🇸",
    "United States": "🇺🇸",
    "Mexico City": "🇲🇽",
    "Mexico": "🇲🇽",
    "São Paulo": "🇧🇷",
    "Brazil": "🇧🇷",
    "Las Vegas": "🇺🇸",
    "Qatar": "🇶🇦",
    "Abu Dhabi": "🇦🇪",
    "UAE": "🇦🇪"
}

def get_calendar(year: int) -> list:
    """
    Fetch the calendar schedule for a given year.
    Returns a list of dicts with round info, flag, and completed status.
    """
    cache_path = Path("data/fastf1_cache")
    cache_path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_path))
    
    console.print(f"[dim]Fetching F1 {year} calendar...[/dim]")
    schedule = fastf1.get_event_schedule(year)
    races = schedule[schedule["EventFormat"] != "testing"].copy()
    
    now = pd.Timestamp.now(tz='UTC')
    calendar_list = []
    
    for _, race in races.iterrows():
        round_num = int(race["RoundNumber"])
        race_name = race["EventName"].replace(" Grand Prix", "")
        country = race["Country"]
        circuit = race["Location"]
        
        race_date = race["Session5Date"]
        completed = False
        if not pd.isna(race_date) and pd.Timestamp(race_date) < now:
            completed = True
            
        flag = COUNTRY_FLAGS.get(country, COUNTRY_FLAGS.get(race_name, "🏁"))
        
        calendar_list.append({
            "round": round_num,
            "name": race_name,
            "country": country,
            "flag": flag,
            "circuit": circuit,
            "type": CIRCUIT_TYPES.get(race_name, "balanced"),
            "completed": completed,
            "date": str(race_date) if not pd.isna(race_date) else ""
        })
        
    return calendar_list

def get_all_results(years=[2024, 2025, 2026]) -> pd.DataFrame:
    """
    Load all completed race results for the specified years.
    Uses data/raw_results.csv as a cache to prevent network requests.
    Automatically fetches new completed races.
    """
    cache_file = Path("data/raw_results.csv")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    fastf1_cache = Path("data/fastf1_cache")
    fastf1_cache.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(fastf1_cache))
    
    cached_df = pd.DataFrame()
    if cache_file.exists():
        try:
            cached_df = pd.read_csv(cache_file)
        except Exception as e:
            console.print(f"[red]Error reading raw results cache, will rebuild: {e}[/red]")
            
    now = pd.Timestamp.now(tz='UTC')
    missing_races = []
    
    for year in years:
        try:
            schedule = fastf1.get_event_schedule(year)
            races = schedule[schedule["EventFormat"] != "testing"].copy()
            
            for _, race in races.iterrows():
                round_num = int(race["RoundNumber"])
                race_name = race["EventName"].replace(" Grand Prix", "")
                
                race_date = race["Session5Date"]
                if pd.isna(race_date):
                    continue
                if pd.Timestamp(race_date) > now:
                    continue
                    
                # Check if this race is already in cached_df
                if not cached_df.empty:
                    exists = ((cached_df["year"] == year) & (cached_df["round"] == round_num)).any()
                    if exists:
                        continue
                        
                missing_races.append((year, round_num, race_name))
        except Exception as e:
            console.print(f"[red]Error fetching schedule for {year}: {e}[/red]")
            
    if missing_races:
        console.print(f"[bold cyan]Found {len(missing_races)} completed races missing from cache. Downloading...[/bold cyan]")
        new_results = []
        for year, round_num, race_name in missing_races:
            try:
                console.print(f"Downloading {year} Round {round_num} ({race_name}) results...")
                session = fastf1.get_session(year, round_num, "R")
                session.load(laps=False, telemetry=False, weather=False, messages=False)
                
                results = session.results.copy()
                for _, r in results.iterrows():
                    new_results.append({
                        "year": year,
                        "round": round_num,
                        "race_name": race_name,
                        "circuit_type": CIRCUIT_TYPES.get(race_name, "balanced"),
                        "driver": r.get("Abbreviation"),
                        "fullName": r.get("FullName"),
                        "team": r.get("TeamName"),
                        "position": pd.to_numeric(r.get("Position"), errors="coerce"),
                        "grid_pos": pd.to_numeric(r.get("GridPosition"), errors="coerce"),
                        "points": pd.to_numeric(r.get("Points"), errors="coerce"),
                        "status": r.get("Status")
                    })
            except Exception as e:
                console.print(f"[yellow]Skipping Round {round_num} ({race_name}): {e}[/yellow]")
                
        if new_results:
            new_df = pd.DataFrame(new_results)
            if cached_df.empty:
                cached_df = new_df
            else:
                cached_df = pd.concat([cached_df, new_df], ignore_index=True)
            cached_df = cached_df.sort_values(by=["year", "round", "position"]).reset_index(drop=True)
            cached_df.to_csv(cache_file, index=False)
            console.print(f"[green]Saved updated raw results to {cache_file}[/green]")
            
    return cached_df

def load_season_results(year: int = 2024) -> pd.DataFrame:
    """
    Fetch the results of all completed races for a given season from cache or FastF1.
    """
    df = get_all_results(years=[year])
    if not df.empty:
        df = df[df["year"] == year].reset_index(drop=True)
    return df

def generate_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute rolling features for each driver and team to capture recent form,
    cumulative standings, and track history. Handles dummy rows seamlessly.
    """
    if df.empty:
        return df

    # Sort to compute rolling features correctly
    df = df.sort_values(by=["driver", "year", "round"]).reset_index(drop=True)

    # ── Driver Stats ──────────────────────────────────────────
    # Cumulative points and wins before the current round (using shift)
    df["driver_cum_points"] = df.groupby("driver")["points"].transform(
        lambda x: x.cumsum().shift(1).fillna(0)
    )
    df["driver_cum_wins"] = df.groupby("driver")["position"].transform(
        lambda x: (x == 1).cumsum().shift(1).fillna(0)
    )
    
    # Recent finishing form (average of last 3 races)
    df["driver_recent_avg_finish"] = df.groupby("driver")["position"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean().fillna(10)
    )
    # Recent qualifying form
    df["driver_recent_avg_grid"] = df.groupby("driver")["grid_pos"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean().fillna(10)
    )

    # ── Team Stats ────────────────────────────────────────────
    # Team cumulative points before the current round
    df = df.sort_values(by=["team", "year", "round"]).reset_index(drop=True)
    
    team_round_points = df.groupby(["team", "year", "round"])["points"].sum().reset_index()
    team_round_points = team_round_points.sort_values(by=["team", "year", "round"])
    team_round_points["team_cum_points"] = team_round_points.groupby("team")["points"].transform(
        lambda x: x.cumsum().shift(1).fillna(0)
    )
    
    # Merge team cumulative points back
    df = df.merge(team_round_points[["team", "year", "round", "team_cum_points"]], on=["team", "year", "round"], how="left")

    # Team recent average finish
    team_round_finish = df.groupby(["team", "year", "round"])["position"].mean().reset_index()
    team_round_finish = team_round_finish.sort_values(by=["team", "year", "round"])
    team_round_finish["team_recent_avg_finish"] = team_round_finish.groupby("team")["position"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean().fillna(10)
    )
    df = df.merge(team_round_finish[["team", "year", "round", "team_recent_avg_finish"]], on=["team", "year", "round"], how="left")

    # Re-sort to standard chronological view
    # Group dummy rows (position NaN) at the bottom or sort by grid
    df["is_dummy"] = df["position"].isna()
    df = df.sort_values(by=["year", "round", "is_dummy", "position", "grid_pos"]).reset_index(drop=True)
    
    # For training safety, fillna of the feature columns
    df["grid_pos"] = df["grid_pos"].fillna(20)
    
    return df
