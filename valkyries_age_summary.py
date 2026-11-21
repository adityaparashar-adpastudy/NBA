"""
WNBA AGE Summary - Golden State Valkyries (2025 Season)
---------------------------------------------------------
Produces the same summary metrics as NBA_Injury_Rate_Summary_v5.pdf,
computed from ESPN's WNBA box score data:

  Regular season games
  Standard game length
  Games that went to overtime
  Total minutes played (season)
  Minutes per game (avg.)
  Total players rostered (season)
  Players rostered per game (avg.)
  Players entered individual games (AGE)
  Players entered per game (avg.)
  Injuries recorded

No API key required. Undocumented endpoint - if parsing breaks, print
raw box score JSON for one game and inspect the players[] structure.
"""

import requests
import pandas as pd
import time

TEAM_SLUG = "gs"          # Golden State Valkyries - ESPN abbreviation
TEAM_NAME = "Golden State Valkyries"
SEASON_YEAR = 2025
SEASON_TYPE = 2            # 2 = regular season
STANDARD_GAME_LENGTH = 200  # WNBA regulation = 4 x 10 min quarters = 40 min/team-minutes = 200 total (5 players x 40)

SCHEDULE_URL = f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{TEAM_SLUG}/schedule"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"


def fetch_schedule(season_year: int, season_type: int) -> list:
    resp = requests.get(SCHEDULE_URL, params={"season": season_year, "seasontype": season_type}, timeout=15)
    resp.raise_for_status()
    events = resp.json().get("events", [])
    return [
        e["id"] for e in events
        if e.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("completed")
    ]


def fetch_boxscore(game_id: str) -> dict:
    resp = requests.get(SUMMARY_URL, params={"event": game_id}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def game_stats(boxscore: dict, team_name: str) -> dict:
    """Per-game numbers needed to build the season summary."""
    minutes_total = 0.0
    rostered = 0
    entered = 0
    dnp_injury_count = 0

    for team_block in boxscore.get("boxscore", {}).get("players", []):
        if team_name.lower() not in team_block.get("team", {}).get("displayName", "").lower():
            continue
        for stat_group in team_block.get("statistics", []):
            labels = stat_group.get("names") or stat_group.get("labels") or []
            min_idx = labels.index("MIN") if "MIN" in labels else None
            for athlete_entry in stat_group.get("athletes", []):
                rostered += 1
                stats = athlete_entry.get("stats", [])
                did_not_play = athlete_entry.get("didNotPlay", False) or not stats
                reason = (athlete_entry.get("reason") or "").upper()

                if not did_not_play:
                    entered += 1
                    if min_idx is not None and min_idx < len(stats):
                        try:
                            minutes_total += float(stats[min_idx])
                        except ValueError:
                            pass
                elif "INJURY" in reason or any(
                    kw in reason for kw in ["HAMSTRING", "KNEE", "ANKLE", "ACL", "CONCUSSION", "BACK", "SHOULDER", "ILLNESS"]
                ):
                    dnp_injury_count += 1

    went_ot = minutes_total > STANDARD_GAME_LENGTH
    return {
        "minutes": minutes_total,
        "rostered": rostered,
        "entered": entered,
        "injuries": dnp_injury_count,
        "overtime": went_ot,
    }


def main():
    print(f"Fetching {SEASON_YEAR} schedule for {TEAM_NAME}...")
    game_ids = fetch_schedule(SEASON_YEAR, SEASON_TYPE)
    n_games = len(game_ids)
    print(f"Found {n_games} completed games.")

    totals = {"minutes": 0.0, "rostered": 0, "entered": 0, "injuries": 0, "overtime": 0}

    for i, gid in enumerate(game_ids, 1):
        print(f"  [{i}/{n_games}] game {gid}...")
        try:
            box = fetch_boxscore(gid)
            g = game_stats(box, TEAM_NAME)
            totals["minutes"] += g["minutes"]
            totals["rostered"] += g["rostered"]
            totals["entered"] += g["entered"]
            totals["injuries"] += g["injuries"]
            totals["overtime"] += int(g["overtime"])
        except Exception as e:
            print(f"    Failed on game {gid}: {e}")
        time.sleep(0.5)

    summary = {
        "Regular season games": n_games,
        "Standard game length": f"{STANDARD_GAME_LENGTH} minutes",
        "Games that went to overtime": totals["overtime"],
        "Total minutes played (season)": round(totals["minutes"], 1),
        "Minutes per game (avg.)": round(totals["minutes"] / n_games, 2) if n_games else None,
        "Total players rostered (season)": totals["rostered"],
        "Players rostered per game (avg.)": round(totals["rostered"] / n_games, 2) if n_games else None,
        "Players entered individual games (AGE)": totals["entered"],
        "Players entered per game (avg.)": round(totals["entered"] / n_games, 2) if n_games else None,
        "Injuries recorded": totals["injuries"],
    }

    df = pd.DataFrame(list(summary.items()), columns=["Metric", "Value"])
    out_path = f"valkyries_{SEASON_YEAR}_AGE_summary.csv"
    df.to_csv(out_path, index=False)

    print(f"\n{TEAM_NAME}")
    print(df.to_string(index=False))
    print(f"\nSaved to {out_path}")
    print(
        "\nNote: 'overtime' is a proxy (season minutes exceeding standard game length), "
        "same caveat as the NBA version - worth a manual spot-check. "
        "'Injuries recorded' counts DNP reasons containing an injury keyword; "
        "coach's-decision DNPs are excluded."
    )


if __name__ == "__main__":
    main()
