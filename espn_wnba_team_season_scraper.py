"""
ESPN WNBA Team Season Availability Scraper
-------------------------------------------
Pulls every game a team played in a given season and extracts per-player
availability status from ESPN's box score data - including DNP reasons
(e.g. "DNP-RIGHT KNEE INJURY", "DNP-COACH'S DECISION"), which ESPN includes
for WNBA box scores but Basketball-Reference does NOT.

This replaces the roster-vs-box-score diff workaround: ESPN's box scores
already carry the "reason" text we couldn't get from Basketball-Reference.

Usage:
    python3 espn_wnba_team_season_scraper.py

No API key required. Endpoint is undocumented - fields may shift without
notice, so if parsing breaks, print raw_summary and inspect the boxscore
players[] structure directly.
"""

import requests
import pandas as pd
import time

TEAM_SLUG = "gs"          # Golden State Valkyries - ESPN abbreviation
TEAM_NAME = "Golden State Valkyries"
SEASON_YEAR = 2025
SEASON_TYPE = 2           # 2 = regular season, 3 = postseason

SCHEDULE_URL = f"https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{TEAM_SLUG}/schedule"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"


def fetch_schedule(season_year: int, season_type: int) -> list:
    """Get all game IDs for the team's season."""
    resp = requests.get(SCHEDULE_URL, params={"season": season_year, "seasontype": season_type}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    events = data.get("events", [])
    games = []
    for e in events:
        comp = e.get("competitions", [{}])[0]
        if not comp.get("status", {}).get("type", {}).get("completed"):
            continue
        competitors = comp.get("competitors", [])
        our_side = next((c for c in competitors if c.get("team", {}).get("abbreviation", "").lower() == TEAM_SLUG), None)
        opp_side = next((c for c in competitors if c is not our_side), None)
        games.append({
            "game_id": e["id"],
            "date": e.get("date"),
            "name": e.get("name"),
            "opponent": opp_side.get("team", {}).get("displayName") if opp_side else None,
            "home_away": our_side.get("homeAway") if our_side else None,
        })
    return games


def fetch_boxscore(game_id: str) -> dict:
    resp = requests.get(SUMMARY_URL, params={"event": game_id}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_team_availability(boxscore: dict, team_name: str, game_id: str, game_date: str,
                             opponent: str = None, home_away: str = None) -> list:
    """
    Walks boxscore['boxscore']['players'] to find our team's player list,
    then pulls the FULL stat line per player (same columns ESPN shows in
    the box score UI: MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK, OREB,
    DREB, PF, +/-), plus status (Played/DNP) and DNP reason when present.

    ESPN's statistics[0] block carries a "names"/"labels" array that maps
    1:1 to each athlete's "stats" array - we use that mapping instead of
    hardcoding column order, since it can vary slightly by game.
    """
    rows = []
    for team_block in boxscore.get("boxscore", {}).get("players", []):
        if team_name.lower() not in team_block.get("team", {}).get("displayName", "").lower():
            continue

        for stat_group in team_block.get("statistics", []):
            # e.g. ["MIN","FG","3PT","FT","OREB","DREB","REB","AST","STL","BLK","TO","PF","+/-","PTS"]
            stat_labels = stat_group.get("names") or stat_group.get("labels") or []

            for athlete_entry in stat_group.get("athletes", []):
                athlete = athlete_entry.get("athlete", {})
                stats = athlete_entry.get("stats", [])
                dnp_reason = athlete_entry.get("reason")
                did_not_play = athlete_entry.get("didNotPlay", False) or (not stats and dnp_reason)

                row = {
                    "game_id": game_id,
                    "date": game_date,
                    "opponent": opponent,
                    "home_away": home_away,
                    "player": athlete.get("displayName"),
                    "player_id": athlete.get("id"),
                    "position": athlete.get("position", {}).get("abbreviation"),
                    "starter": athlete_entry.get("starter", False),
                    "status": "DNP" if did_not_play else "Played",
                    "dnp_reason": dnp_reason if did_not_play else None,
                }

                # Zip labels <-> values so every stat lands in its own named column
                if not did_not_play:
                    for label, value in zip(stat_labels, stats):
                        row[label] = value

                rows.append(row)
    return rows


def main():
    print(f"Fetching {SEASON_YEAR} schedule for {TEAM_NAME}...")
    games = fetch_schedule(SEASON_YEAR, SEASON_TYPE)
    print(f"Found {len(games)} completed games.")

    all_rows = []
    for i, g in enumerate(games, 1):
        print(f"  [{i}/{len(games)}] Pulling box score for game {g['game_id']} ({g['name']})...")
        try:
            box = fetch_boxscore(g["game_id"])
            rows = parse_team_availability(
                box, TEAM_NAME, g["game_id"], g["date"],
                opponent=g.get("opponent"), home_away=g.get("home_away"),
            )
            all_rows.extend(rows)
        except Exception as e:
            print(f"    Failed on game {g['game_id']}: {e}")
        time.sleep(0.5)  # be polite to an undocumented endpoint

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("No rows parsed - check boxscore JSON shape (see docstring).")
        return

    out_path = f"valkyries_{SEASON_YEAR}_full_stats.csv"
    df.to_csv(out_path, index=False)
    print(f"\nSaved {len(df)} player-game rows to {out_path}")
    print(f"Columns: {list(df.columns)}")
    print("\nSample DNP rows:")
    print(df[df["status"] == "DNP"].head(10).to_string(index=False))
    print("\nSample played rows:")
    print(df[df["status"] == "Played"].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
