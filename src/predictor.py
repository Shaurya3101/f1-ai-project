# src/predictor.py
import fastf1
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from src.features import get_all_results, generate_features, get_calendar, CIRCUIT_TYPES
from rich.console import Console

console = Console()

MODEL_PATH = Path("data/predictor_model.pkl")

# Map circuit types to numbers for ML
CIRCUIT_TYPE_MAP = {"balanced": 0, "street": 1, "high_speed": 2}

FEATURE_COLS = [
    "grid_pos",
    "driver_cum_points",
    "driver_cum_wins",
    "driver_recent_avg_finish",
    "driver_recent_avg_grid",
    "team_cum_points",
    "team_recent_avg_finish",
    "circuit_type_code"
]

def predict_race_winner(
    year: int, 
    round_num: int, 
    custom_grid: dict = None
) -> list:
    """
    Predict the outcome of a race.
    
    Args:
        year: e.g. 2026
        round_num: round number
        custom_grid: dictionary mapping driver abbreviation (e.g. 'VER') to grid position (e.g. 1)
        
    Returns:
        List of dictionaries with drivers, predicted positions, and winning probabilities.
    """
    console.print(f"[bold cyan]Running AI prediction for {year} Round {round_num}...[/bold cyan]")
    
    # 1. Load all raw results from cache
    raw_results = get_all_results(years=[2024, 2025, 2026])
    
    if raw_results.empty:
        raise ValueError("No data available to train the model. Check internet/cache.")

    # 2. Find the target race info from the schedule
    calendar = get_calendar(year)
    target_race = next((r for r in calendar if r["round"] == round_num), None)
    if not target_race:
        raise ValueError(f"Round {round_num} not found in the {year} calendar.")

    race_name = target_race["name"]
    circuit_type = target_race["type"]
    
    # 3. Filter raw results to only include races that occurred BEFORE the target race
    # i.e., past years, or same year but earlier rounds
    historical_results = raw_results[
        (raw_results["year"] < year) | 
        ((raw_results["year"] == year) & (raw_results["round"] < round_num))
    ].copy()

    # 4. Get the active drivers list for the target race
    driver_list = []
    
    # Try to load qualifying results for the target session if they exist
    try:
        session = fastf1.get_session(year, round_num, "Q")
        # Load without telemetry/laps/etc to make it super fast
        session.load(laps=False, telemetry=False, weather=False, messages=False)
        results = session.results
        if not results.empty:
            console.print("[green]Qualifying results found. Using official grid...[/green]")
            for _, r in results.iterrows():
                driver_list.append({
                    "driver": r.get("Abbreviation"),
                    "fullName": r.get("FullName"),
                    "team": r.get("TeamName"),
                    "grid_pos": pd.to_numeric(r.get("Position"), errors="coerce")
                })
    except Exception as e:
        console.print(f"[dim]Qualifying results not yet available or empty: {e}[/dim]")

    # If qualifying is not available, get driver line-up from the latest completed round
    if not driver_list:
        latest_round = raw_results[raw_results["year"] == year]["round"].max()
        # Fall back to previous year if no races completed in this year yet
        latest_year = year
        if pd.isna(latest_round):
            latest_year = year - 1
            latest_round = raw_results[raw_results["year"] == latest_year]["round"].max()
            
        console.print(f"[yellow]Grid not available. Copying lineup from {latest_year} Round {latest_round}...[/yellow]")
        latest_drivers_df = raw_results[
            (raw_results["year"] == latest_year) & 
            (raw_results["round"] == latest_round)
        ]
        
        # Sort these drivers by championship standing or finish positions for a logical default grid
        # We'll compute standings from historical_results for the current year
        year_results = historical_results[historical_results["year"] == year]
        if not year_results.empty:
            standings = year_results.groupby("driver")["points"].sum().reset_index()
            standings = standings.sort_values(by="points", ascending=False).reset_index(drop=True)
            standings_map = {r["driver"]: idx + 1 for idx, r in standings.iterrows()}
        else:
            standings_map = {}
            
        for idx, r in latest_drivers_df.iterrows():
            d_code = r.get("driver")
            # Default grid position is standings position, or list index if not in standings
            default_grid = standings_map.get(d_code, len(driver_list) + 1)
            driver_list.append({
                "driver": d_code,
                "fullName": r.get("fullName"),
                "team": r.get("team"),
                "grid_pos": default_grid
            })
            
        # Re-sort driver list by default_grid and re-number 1 to N
        driver_list = sorted(driver_list, key=lambda x: x["grid_pos"])
        for idx, d in enumerate(driver_list):
            d["grid_pos"] = idx + 1

    # 5. Apply custom grid overrides if provided
    if custom_grid:
        for d in driver_list:
            d_code = d["driver"]
            if d_code in custom_grid:
                d["grid_pos"] = custom_grid[d_code]
        # Re-sort driver_list by grid_pos
        driver_list = sorted(driver_list, key=lambda x: x["grid_pos"])

    # 6. Create dummy rows for the target race
    dummy_rows = []
    for d in driver_list:
        dummy_rows.append({
            "year": year,
            "round": round_num,
            "race_name": race_name,
            "circuit_type": circuit_type,
            "driver": d["driver"],
            "fullName": d["fullName"],
            "team": d["team"],
            "position": np.nan,  # Prediction target
            "grid_pos": d["grid_pos"],
            "points": np.nan,
            "status": "Finished"
        })
        
    dummy_df = pd.DataFrame(dummy_rows)
    
    # 7. Combine historical results and dummy rows, then generate rolling features
    combined_df = pd.concat([historical_results, dummy_df], ignore_index=True)
    combined_df = generate_features(combined_df)
    
    # Map circuit types to code
    combined_df["circuit_type_code"] = combined_df["circuit_type"].map(CIRCUIT_TYPE_MAP).fillna(0)
    
    # 8. Split back into training set and prediction set
    # The prediction set corresponds to the dummy rows (where position is NaN or is_dummy is True)
    train_df = combined_df[~combined_df["is_dummy"]].copy()
    pred_df = combined_df[combined_df["is_dummy"]].copy()
    
    if train_df.empty:
        # If no prior historical data, fall back to simple defaults
        raise ValueError("Historical training data is empty. Cannot train predictor.")
        
    # 9. Train Random Forest on the historical data
    X_train = train_df[FEATURE_COLS]
    y_train = train_df["position"]
    
    # Fillna just in case
    X_train = X_train.fillna(0)
    y_train = y_train.fillna(20)
    
    model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    
    # 10. Predict on the target round
    X_pred = pred_df[FEATURE_COLS].fillna(0)
    predicted_positions = model.predict(X_pred)
    pred_df["predicted_position"] = predicted_positions
    
    # Convert predicted positions to winning probability (softmax over negative predicted positions)
    # Scale temperature
    T = 2.0
    raw_scores = -pred_df["predicted_position"] / T
    exp_scores = np.exp(raw_scores - np.max(raw_scores))
    probabilities = exp_scores / np.sum(exp_scores)
    pred_df["win_probability"] = probabilities * 100
    
    # Sort predictions by predicted position (lower is better)
    pred_df = pred_df.sort_values(by="predicted_position").reset_index(drop=True)
    
    predictions = []
    for idx, r in pred_df.iterrows():
        predictions.append({
            "rank": idx + 1,
            "driver": r["driver"],
            "fullName": r["fullName"],
            "team": r["team"],
            "grid": int(r["grid_pos"]),
            "predicted_pos": round(float(r["predicted_position"]), 1),
            "win_prob": round(float(r["win_probability"]), 1),
            "recent_avg_finish": round(float(r["driver_recent_avg_finish"]), 1),
            "recent_avg_grid": round(float(r["driver_recent_avg_grid"]), 1),
            "cum_points": int(r["driver_cum_points"]),
            "cum_wins": int(r["driver_cum_wins"]),
            "team_cum_points": int(r["team_cum_points"]),
            "team_recent_avg_finish": round(float(r["team_recent_avg_finish"]), 1),
            "circuit_type": str(r["circuit_type"]),
            "circuit_type_code": int(r["circuit_type_code"])
        })
        
    return predictions

if __name__ == "__main__":
    print("Testing dynamic predictor...")
    # Predict 2026 Canadian GP (Round 5)
    preds = predict_race_winner(2026, 5)
    for p in preds[:5]:
         print(f"{p['rank']}. {p['driver']} ({p['team']}) - Grid: {p['grid']} - Pred Pos: {p['predicted_pos']} - Win Prob: {p['win_prob']}%")
