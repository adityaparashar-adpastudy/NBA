"""
NBA Game Data Collector
=======================
Pulls per-game data for all 4 metrics:
  1. Injuries (pre-game report)
  2. Minutes played per game
  3. Players who entered each game
  4. Players on roster eligible to play

Requirements:
    pip install nba_api pandas requests

Usage:
    python nba_data_collector.py
    python nba_data_collector.py --team LAL --season 2024
    python nba_data_collector.py --game_id 0022401001
"""

import argparse
import time
import pandas as pd
import requests
from datetime import datetime

from nba_api.stats.endpoints import (
    leaguegamelog,
    boxscoretraditionalv2,
    commonteamroster,
    leaguedashteamstats,
)
from nba_api.stats.static import teams


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def get_team_id(abbreviation: str) -> str:
    """Convert team abbreviation (e.g. 'LAL') to NBA team ID."""
    nba_teams = teams.get_teams()
    match = [t for t in nba_teams if t["abbreviation"].upper() == abbreviation.upper()]
    if not match:
        raise ValueError(f"Team '{abbreviation}' not found. Use standard NBA abbreviation.")
    return match[0]["id"]


def safe_request(fn, *args, delay=0.6, **kwargs):
    """Wrap nba_api calls with a polite delay to avoid rate-limiting."""
    time.sleep(delay)
    return fn(*args, **kwargs)


# ─────────────────────────────────────────────
# Metric 1: Injuries (pre-game)
# ─────────────────────────────────────────────

def get_injury_report() -> pd.DataFrame:
    """
    Fetches today's official NBA injury report directly from NBA.com.
    Returns a DataFrame with player name, team, status, and reason.

    Note: The official injury report PDF is updated continuously on game days.
    This pulls the structured JSON version used by NBA.com internally.
    """
    url = "https://cdn.nba.com/static/json/liveData/injuryreport/injuryreport.json"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.nba.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        records = []
        for team_entry in data.get("injuryReport", {}).get("injuries", []):
            team_name = team_entry.get("teamName")
            for player in team_entry.get("players", []):
                records.append({
                    "team": team_name,
                    "player": player.get("playerName"),
                    "status": player.get("status"),          # Out / Doubtful / Questionable
                    "reason": player.get("playerStatus"),    # Injury description
                    "game_date": data.get("injuryReport", {}).get("date"),
                })
        return pd.DataFrame(records)

    except Exception as e:
        print(f"[Injury] Could not fetch injury report: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# Metric 2: Minutes played per game
# ─────────────────────────────────────────────

def get_minutes_per_game(game_id: str) -> dict:
    """
    Returns total team minutes played for both teams in a game.
    Regulation = 240 min per team (48 × 5). Each OT period adds 25 min.

    Args:
        game_id: NBA game ID string (e.g. '0022401001')

    Returns:
        dict with keys: game_id, home_team, away_team,
                        home_total_minutes, away_total_minutes, overtime_periods
    """
    box = safe_request(
        boxscoretraditionalv2.BoxScoreTraditionalV2,
        game_id=game_id
    )
    player_stats = box.player_stats.get_data_frame()

    def parse_min(m):
        """Convert 'MM:SS' string to float minutes."""
        if pd.isna(m) or m == "":
            return 0.0
        parts = str(m).split(":")
        return int(parts[0]) + int(parts[1]) / 60

    player_stats["MIN_FLOAT"] = player_stats["MIN"].apply(parse_min)

    summary = (
        player_stats.groupby(["TEAM_ABBREVIATION", "TEAM_ID"])["MIN_FLOAT"]
        .sum()
        .reset_index()
    )

    result = {"game_id": game_id, "teams": []}
    for _, row in summary.iterrows():
        total = round(row["MIN_FLOAT"], 1)
        ot_periods = max(0, round((total - 240) / 25)) if total > 240 else 0
        result["teams"].append({
            "team": row["TEAM_ABBREVIATION"],
            "total_minutes": total,
            "overtime_periods": ot_periods,
        })

    return result


# ─────────────────────────────────────────────
# Metric 3: Players who entered each game
# ─────────────────────────────────────────────

def get_players_who_played(game_id: str) -> pd.DataFrame:
    """
    Returns all players who logged at least 1 second of game time.
    Excludes DNP (Did Not Play) entries.

    Args:
        game_id: NBA game ID string

    Returns:
        DataFrame with player name, team, minutes, points, and entry status
    """
    box = safe_request(
        boxscoretraditionalv2.BoxScoreTraditionalV2,
        game_id=game_id
    )
    df = box.player_stats.get_data_frame()

    # Players who actually entered have non-null MIN and it's not "0:00"
    played = df[df["MIN"].notna() & (df["MIN"] != "") & (df["MIN"] != "0:00")].copy()

    return played[[
        "TEAM_ABBREVIATION", "PLAYER_NAME", "MIN",
        "PTS", "REB", "AST", "START_POSITION"
    ]].rename(columns={
        "TEAM_ABBREVIATION": "team",
        "PLAYER_NAME": "player",
        "MIN": "minutes",
        "PTS": "pts",
        "REB": "reb",
        "AST": "ast",
        "START_POSITION": "position_started",
    })


def get_player_counts_per_game(game_id: str) -> dict:
    """
    Returns count of players who actually entered the game, per team.
    """
    df = get_players_who_played(game_id)
    counts = df.groupby("team")["player"].count().to_dict()
    return {"game_id": game_id, "players_who_played": counts}


# ─────────────────────────────────────────────
# Metric 4: Roster eligible to enter each game
# ─────────────────────────────────────────────

def get_eligible_roster(team_id: str, season: str = "2024-25") -> pd.DataFrame:
    """
    Returns full active roster for a team.
    Cross-reference with injury report to find truly eligible players.

    NBA rules: max 15 on active roster, max 13 can dress for a game.
    Two-way players have eligibility restrictions (45 game days per season).

    Args:
        team_id: NBA team ID (int or str)
        season:  Season string like '2024-25'

    Returns:
        DataFrame of roster with player details
    """
    roster_ep = safe_request(
        commonteamroster.CommonTeamRoster,
        team_id=team_id,
        season=season
    )
    roster = roster_ep.common_team_roster.get_data_frame()

    return roster[[
        "PLAYER", "NUM", "POSITION", "HEIGHT", "WEIGHT",
        "BIRTH_DATE", "EXP", "HOW_ACQUIRED"
    ]].rename(columns={"PLAYER": "player_name", "NUM": "jersey"})


def get_eligible_count_with_injuries(team_id: str, team_name: str, season: str = "2024-25") -> dict:
    """
    Combines roster + injury report to estimate truly available players.

    Returns:
        dict with full_roster_count, injured_out_count, estimated_available
    """
    roster_df = get_eligible_roster(team_id, season)
    injury_df = get_injury_report()

    full_count = len(roster_df)

    if not injury_df.empty:
        # Players listed as 'Out' for this team
        team_injuries = injury_df[
            (injury_df["team"].str.contains(team_name, case=False, na=False)) &
            (injury_df["status"] == "Out")
        ]
        out_count = len(team_injuries)
    else:
        out_count = 0
        team_injuries = pd.DataFrame()

    return {
        "team_id": team_id,
        "full_roster": full_count,
        "out_injured": out_count,
        "estimated_eligible": full_count - out_count,
        "out_players": team_injuries["player"].tolist() if not team_injuries.empty else [],
    }


# ─────────────────────────────────────────────
# Combined: Full game snapshot
# ─────────────────────────────────────────────

def full_game_snapshot(game_id: str, season: str = "2024-25") -> dict:
    """
    Pulls all 4 metrics for a single game.
    Returns a structured dict ready for analysis or export.
    """
    print(f"\nFetching game snapshot for game_id: {game_id}")

    # Metric 2: Minutes
    print("  → Minutes played...")
    minutes = get_minutes_per_game(game_id)

    # Metric 3: Players who entered
    print("  → Players who entered...")
    players_played = get_players_who_played(game_id)
    played_counts = players_played.groupby("team")["player"].count().to_dict()

    # Metric 4: Roster eligibility (needs team IDs from the boxscore)
    box = safe_request(
        boxscoretraditionalv2.BoxScoreTraditionalV2,
        game_id=game_id
    )
    game_summary = box.game_summary.get_data_frame()
    home_team_id = game_summary["HOME_TEAM_ID"].iloc[0]
    away_team_id = game_summary["VISITOR_TEAM_ID"].iloc[0]

    home_abbr = players_played[players_played["team"] == players_played["team"].unique()[0]]["team"].iloc[0]
    away_abbr = players_played["team"].unique()[1] if len(players_played["team"].unique()) > 1 else ""

    print("  → Roster eligibility...")
    home_eligible = get_eligible_count_with_injuries(home_team_id, home_abbr, season)
    away_eligible = get_eligible_count_with_injuries(away_team_id, away_abbr, season)

    return {
        "game_id": game_id,
        "minutes_by_team": minutes["teams"],
        "players_who_played": played_counts,
        "home_team": {
            "team_id": home_team_id,
            **home_eligible,
            "players_entered": played_counts.get(home_abbr, "N/A"),
        },
        "away_team": {
            "team_id": away_team_id,
            **away_eligible,
            "players_entered": played_counts.get(away_abbr, "N/A"),
        },
        "player_log": players_played.to_dict(orient="records"),
    }


# ─────────────────────────────────────────────
# Season-level: multiple games
# ─────────────────────────────────────────────

def get_season_game_ids(team_id: str = None, season: str = "2024-25") -> pd.DataFrame:
    """
    Returns all game IDs for a season (optionally filtered by team).
    Use these IDs to feed into full_game_snapshot() in a loop.
    """
    log = safe_request(
        leaguegamelog.LeagueGameLog,
        season=season,
        season_type_all_star="Regular Season"
    )
    df = log.get_data_frames()[0]

    if team_id:
        df = df[df["TEAM_ID"] == int(team_id)]

    return df[["GAME_ID", "GAME_DATE", "TEAM_ABBREVIATION", "MATCHUP", "WL"]].drop_duplicates()


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NBA Game Data Collector")
    parser.add_argument("--game_id", type=str, help="Specific NBA game ID")
    parser.add_argument("--team", type=str, help="Team abbreviation (e.g. LAL, GSW)")
    parser.add_argument("--season", type=str, default="2024-25", help="Season (e.g. 2024-25)")
    parser.add_argument("--injury_only", action="store_true", help="Only fetch today's injury report")
    args = parser.parse_args()

    if args.injury_only:
        print("\n── Today's NBA Injury Report ──")
        injuries = get_injury_report()
        if injuries.empty:
            print("No injury data available.")
        else:
            print(injuries.to_string(index=False))
        return

    if args.game_id:
        snapshot = full_game_snapshot(args.game_id, args.season)
        print("\n── Game Snapshot ──")
        for k, v in snapshot.items():
            if k != "player_log":
                print(f"  {k}: {v}")
        print("\n── Player Log ──")
        df = pd.DataFrame(snapshot["player_log"])
        print(df.to_string(index=False))

    elif args.team:
        team_id = get_team_id(args.team)
        print(f"\n── {args.team} Game IDs ({args.season}) ──")
        games = get_season_game_ids(team_id=team_id, season=args.season)
        print(games.to_string(index=False))
        print(f"\nTotal games found: {len(games)}")
        print("Re-run with --game_id <GAME_ID> to pull full snapshot for a specific game.")

    else:
        print("\nDemo mode: fetching today's injury report...")
        injuries = get_injury_report()
        print(injuries.head(20).to_string(index=False) if not injuries.empty else "No injury data.")
        print("\nTip: run with --team LAL or --game_id 0022401001 for targeted data.")


if __name__ == "__main__":
    main()
