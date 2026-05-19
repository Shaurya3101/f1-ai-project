# main.py
from src.data_loader import (
    load_session, get_lap_data,
    get_race_results, get_tyre_strategy, get_weather
)
from src.visualise import (
    plot_lap_times, plot_tyre_strategy,
    plot_position_changes, plot_tyre_degradation,
    plot_team_pace, plot_race_dashboard
)
from rich.console import Console

console = Console()

# ── Load session (instant — already cached) ──────────
session = load_session(2024, "Bahrain", "R")
laps     = get_lap_data(session)
results  = get_race_results(session)
strategy = get_tyre_strategy(session)

console.print("\n[bold cyan]Generating charts...[/bold cyan]")

# ── Individual charts ────────────────────────────────
plot_lap_times(laps, title_suffix="— 2024 Bahrain GP")
plot_tyre_strategy(strategy, laps, title_suffix="— 2024 Bahrain GP")
plot_position_changes(results, title_suffix="— 2024 Bahrain GP")
plot_tyre_degradation(laps, drivers=["VER", "NOR", "HAM"],
                      title_suffix="— 2024 Bahrain GP")
plot_team_pace(laps, title_suffix="— 2024 Bahrain GP")

# ── Big dashboard (all charts in one) ────────────────
plot_race_dashboard(laps, results, strategy,
                    title_suffix="— 2024 Bahrain GP")

console.print("\n[bold green]All charts saved to data/charts/[/bold green]")
console.print("[dim]Open any .html file in your browser to see interactive charts![/dim]")