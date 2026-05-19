# src/visualise.py
# ─────────────────────────────────────────────
# What this file does:
#   Turns raw DataFrames into interactive charts using Plotly.
#   Every function takes data + saves an HTML file you can open in browser.
# ─────────────────────────────────────────────

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from pathlib import Path
from rich.console import Console

console = Console()

# All charts saved here
OUTPUT_DIR = Path("data/charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# F1 team colours — used in every chart
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

# Tyre compound colours — exact F1 official colours
TYRE_COLORS = {
    "SOFT":   "#FF3333",
    "MEDIUM": "#FFF200",
    "HARD":   "#FFFFFF",
    "INTER":  "#39B54A",
    "WET":    "#0067FF",
}


def _save(fig, filename: str):
    """Save chart as interactive HTML and print path."""
    path = OUTPUT_DIR / filename
    fig.write_html(str(path))
    console.print(f"[bold green]✓ Chart saved:[/] {path}")
    return path


def plot_lap_times(laps: pd.DataFrame, drivers: list = None, title_suffix: str = ""):
    """
    Line chart: lap time progression for selected drivers.
    Shows how pace evolves across the race — tyre deg visible as lines rise.

    Args:
        laps    : output of get_lap_data()
        drivers : list of 3-letter codes e.g. ["VER", "HAM", "NOR"]
                  None = top 5 finishers
    """
    df = laps.copy()

    # Filter to requested drivers
    if drivers:
        df = df[df["Driver"].isin(drivers)]
    else:
        # Auto-pick top 5 by median finishing position
        top5 = (df.groupby("Driver")["Position"]
                  .median()
                  .nsmallest(5)
                  .index.tolist())
        df = df[df["Driver"].isin(top5)]

    # Remove obvious outlier laps (pit in/out, VSC, SC)
    # Keep only laps within 110% of each driver's personal best
    def filter_outliers(group):
        best = group["LapTimeSeconds"].min()
        return group[group["LapTimeSeconds"] <= best * 1.10]

    df = df.groupby("Driver", group_keys=False).apply(filter_outliers)

    fig = px.line(
        df,
        x="LapNumber",
        y="LapTimeSeconds",
        color="Driver",
        markers=True,
        title=f"Lap Time Progression {title_suffix}",
        labels={
            "LapNumber": "Lap",
            "LapTimeSeconds": "Lap Time (seconds)",
            "Driver": "Driver"
        },
        hover_data=["Compound", "TyreLife", "Position"]
    )

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#16213e",
        font_color="white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )

    _save(fig, "lap_times.html")
    return fig


def plot_tyre_strategy(strategy: pd.DataFrame, laps: pd.DataFrame, title_suffix: str = ""):
    """
    Horizontal bar chart showing each driver's tyre strategy.
    Coloured by compound — red=soft, yellow=medium, white=hard.
    This is the classic F1 strategy visualisation.
    """
    # Build per-stint rows for the bar chart
    rows = []
    for _, row in strategy.iterrows():
        driver = row["Driver"]
        compounds = row["Compounds"].split(" → ")
        stint_laps = row["StintLaps"]
        lap_start = 1
        for compound, n_laps in zip(compounds, stint_laps):
            rows.append({
                "Driver":   driver,
                "Compound": compound,
                "LapStart": lap_start,
                "Laps":     n_laps,
            })
            lap_start += n_laps

    df = pd.DataFrame(rows)

    # Sort drivers by finishing position
    finish_order = (laps.groupby("Driver")["Position"]
                        .last()
                        .sort_values()
                        .index.tolist())
    df["Driver"] = pd.Categorical(df["Driver"], categories=finish_order[::-1], ordered=True)
    df = df.sort_values("Driver")

    fig = px.bar(
        df,
        x="Laps",
        y="Driver",
        color="Compound",
        orientation="h",
        base="LapStart",
        color_discrete_map=TYRE_COLORS,
        title=f"Tyre Strategy {title_suffix}",
        labels={"Laps": "Lap Number", "Driver": "Driver"},
        text="Compound"
    )

    fig.update_traces(textposition="inside", textfont_size=10)
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#16213e",
        font_color="white",
        bargap=0.15,
        xaxis_title="Lap Number",
        legend_title="Compound"
    )

    _save(fig, "tyre_strategy.html")
    return fig


def plot_position_changes(results: pd.DataFrame, title_suffix: str = ""):
    """
    Bar chart: positions gained/lost from grid to finish.
    Green = gained positions, Red = lost positions.
    """
    df = results.dropna(subset=["PositionsGained"]).copy()
    df = df.sort_values("PositionsGained", ascending=True)
    df["Color"] = df["PositionsGained"].apply(
        lambda x: "#00C851" if x > 0 else ("#FF4444" if x < 0 else "#AAAAAA")
    )

    fig = go.Figure(go.Bar(
        x=df["PositionsGained"],
        y=df["Abbreviation"],
        orientation="h",
        marker_color=df["Color"],
        text=df["PositionsGained"].apply(lambda x: f"+{int(x)}" if x > 0 else str(int(x))),
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Positions gained: %{x}<br>"
            "<extra></extra>"
        )
    ))

    fig.update_layout(
        title=f"Positions Gained/Lost {title_suffix}",
        template="plotly_dark",
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#16213e",
        font_color="white",
        xaxis_title="Positions Gained (negative = lost)",
        yaxis_title="Driver",
        xaxis=dict(zeroline=True, zerolinecolor="white", zerolinewidth=1)
    )

    _save(fig, "position_changes.html")
    return fig


def plot_tyre_degradation(laps: pd.DataFrame, drivers: list = None, title_suffix: str = ""):
    """
    Scatter plot: lap time vs tyre life, coloured by compound.
    This shows EXACTLY how quickly each tyre compound degrades.
    The slope of each cluster = degradation rate.
    """
    df = laps.copy()

    if drivers:
        df = df[df["Driver"].isin(drivers)]

    # Filter outliers (pit laps etc)
    def filter_outliers(group):
        best = group["LapTimeSeconds"].min()
        return group[group["LapTimeSeconds"] <= best * 1.08]

    df = df.groupby("Driver", group_keys=False).apply(filter_outliers)
    df = df.dropna(subset=["TyreLife", "LapTimeSeconds", "Compound"])

    fig = px.scatter(
        df,
        x="TyreLife",
        y="LapTimeSeconds",
        color="Compound",
        color_discrete_map=TYRE_COLORS,
        facet_col="Driver" if drivers and len(drivers) <= 4 else None,
        trendline="ols",           # linear regression line per compound!
        title=f"Tyre Degradation {title_suffix}",
        labels={
            "TyreLife": "Tyre Age (laps)",
            "LapTimeSeconds": "Lap Time (s)",
        },
        hover_data=["Driver", "LapNumber"]
    )

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#16213e",
        font_color="white",
    )

    _save(fig, "tyre_degradation.html")
    return fig


def plot_team_pace(laps: pd.DataFrame, title_suffix: str = ""):
    """
    Box plot: lap time distribution per team.
    Shows median pace + consistency. Lower box = faster team.
    """
    # Get team info by merging driver → team mapping
    df = laps.copy()

    # Remove outlier laps
    def filter_outliers(group):
        best = group["LapTimeSeconds"].min()
        return group[group["LapTimeSeconds"] <= best * 1.07]

    df = df.groupby("Driver", group_keys=False).apply(filter_outliers)

    # We need team names — get from session results if available
    if "Team" in df.columns:
        team_col = "Team"
    else:
        console.print("[yellow]No Team column in laps — skipping team pace chart[/yellow]")
        return None

    # Sort teams by median lap time
    team_order = (df.groupby(team_col)["LapTimeSeconds"]
                    .median()
                    .sort_values()
                    .index.tolist())

    fig = px.box(
        df,
        x=team_col,
        y="LapTimeSeconds",
        color=team_col,
        color_discrete_map=TEAM_COLORS,
        category_orders={team_col: team_order},
        title=f"Team Pace Comparison {title_suffix}",
        labels={
            "LapTimeSeconds": "Lap Time (s)",
            team_col: "Team"
        },
        points="outliers"
    )

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#16213e",
        font_color="white",
        showlegend=False,
        xaxis_tickangle=45
    )

    _save(fig, "team_pace.html")
    return fig


def plot_race_dashboard(laps: pd.DataFrame, results: pd.DataFrame,
                        strategy: pd.DataFrame, title_suffix: str = ""):
    """
    Combined 2x2 dashboard with all key charts in one view.
    This is the showpiece visualisation for your project.
    """
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Lap Times — Top 5",
            "Positions Gained/Lost",
            "Tyre Strategy",
            "Tyre Degradation — Top 3"
        ),
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )

    # ── Top left: Lap times for top 5 ──
    top5 = (laps.groupby("Driver")["Position"]
                .median()
                .nsmallest(5)
                .index.tolist())

    colors = px.colors.qualitative.Plotly
    for i, driver in enumerate(top5):
        d = laps[laps["Driver"] == driver].copy()
        best = d["LapTimeSeconds"].min()
        d = d[d["LapTimeSeconds"] <= best * 1.10]
        fig.add_trace(go.Scatter(
            x=d["LapNumber"], y=d["LapTimeSeconds"],
            mode="lines+markers", name=driver,
            line=dict(color=colors[i % len(colors)]),
            showlegend=True
        ), row=1, col=1)

    # ── Top right: Positions gained ──
    df_pos = results.dropna(subset=["PositionsGained"]).copy()
    df_pos = df_pos.sort_values("PositionsGained")
    bar_colors = ["#00C851" if x > 0 else "#FF4444" if x < 0 else "#AAAAAA"
                  for x in df_pos["PositionsGained"]]
    fig.add_trace(go.Bar(
        x=df_pos["PositionsGained"],
        y=df_pos["Abbreviation"],
        orientation="h",
        marker_color=bar_colors,
        showlegend=False
    ), row=1, col=2)

    # ── Bottom left: Tyre strategy ──
    rows = []
    finish_order = (laps.groupby("Driver")["Position"]
                        .last().sort_values().index.tolist())
    for _, row in strategy.iterrows():
        compounds = row["Compounds"].split(" → ")
        stint_laps = row["StintLaps"]
        lap_start = 1
        for compound, n_laps in zip(compounds, stint_laps):
            rows.append({
                "Driver": row["Driver"],
                "Compound": compound,
                "LapStart": lap_start,
                "Laps": n_laps
            })
            lap_start += n_laps

    strat_df = pd.DataFrame(rows)
    for compound, color in TYRE_COLORS.items():
        sub = strat_df[strat_df["Compound"] == compound]
        if sub.empty:
            continue
        # Sort by finish order
        sub = sub.copy()
        sub["SortKey"] = sub["Driver"].apply(
            lambda d: finish_order.index(d) if d in finish_order else 99
        )
        sub = sub.sort_values("SortKey", ascending=False)
        fig.add_trace(go.Bar(
            x=sub["Laps"], y=sub["Driver"],
            base=sub["LapStart"],
            orientation="h",
            name=compound,
            marker_color=color,
            showlegend=False
        ), row=2, col=1)

    # ── Bottom right: Tyre degradation top 3 ──
    top3 = top5[:3]
    df_deg = laps[laps["Driver"].isin(top3)].copy()
    for driver in top3:
        d = df_deg[df_deg["Driver"] == driver]
        best = d["LapTimeSeconds"].min()
        d = d[d["LapTimeSeconds"] <= best * 1.08]
        fig.add_trace(go.Scatter(
            x=d["TyreLife"], y=d["LapTimeSeconds"],
            mode="markers", name=f"{driver} deg",
            showlegend=False
        ), row=2, col=2)

    fig.update_layout(
        title_text=f"F1 Race Dashboard {title_suffix}",
        template="plotly_dark",
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#16213e",
        font_color="white",
        height=800,
        barmode="stack"
    )

    _save(fig, "race_dashboard.html")
    return fig