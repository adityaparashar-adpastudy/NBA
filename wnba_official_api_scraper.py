"""
WNBA Roster Availability Scraper - via official stats.wnba.com API
Fever, Sky, Storm, Mercury, 2025 regular season

Uses the same underlying API that stats.wnba.com/stats.nba.com run on
(documented via the wehoop/nba_api open-source projects). This is a real,
different data source from Basketball-Reference, and it solves the problem
BBR had: the official box score endpoint lists every player who was on the
ACTIVE/DRESSED roster for that specific game (not just the season roster),
with a blank MIN field for anyone who dressed but didn't play.

Columns produced:
  Game #, Date, Opp, Result,
  (A) Available - count of player rows in the team's box score for that game
                  (the active/dressed roster for that specific game - this
                  already excludes inactive/not-with-team players, because
                  they never generate a row here)
  (B) Entered    - subset of Available where MIN is non-blank (played any
                  amount of time, even 1 second)
  Minutes        - total team minutes summed across "Entered" rows

(C) In-game injuries are NOT included - as discussed, not reliably derivable
from box score data of any kind (box scores reflect final stats, not
in-game injury events). You mentioned having a separate approach for that,
so this script only produces (A) and (B) plus supporting columns.

IMPORTANT CAVEATS (please read before relying on this):
1. stats.wnba.com is known to be sensitive to request headers and can
   rate-limit or block requests that don't look like a real browser. The
   headers below are the commonly-documented workaround, but if you get
   403s or empty responses, that's what's happening - slow down the
   DELAY_SECONDS and/or add more browser-like headers.
2. I have NOT been able to run this end-to-end myself (stats.wnba.com is
   outside my sandbox's allowed network), so treat this as a first draft
   to debug locally rather than a verified-working script. If the JSON
   response structure differs from what's coded here, print(data) to see
   the actual shape and adjust the parsing.
3. LeagueGameFinder pulls ALL teams' games for the season in one call, then
   filters client-side by team abbreviation - this is intentional, since it
   avoids needing to know each team's internal numeric TeamID.

Requires: requests
Run from your venv: source ~/Downloads/venv/bin/activate
"""

import requests
import time
import csv

# stats.wnba.com requires browser-like headers or it will reject requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.wnba.com/",
    "Origin": "https://www.wnba.com",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

DELAY_SECONDS = 3

TEAMS = {
    "Fever": "IND",
    "Sky": "CHI",
    "Storm": "SEA",
    "Mercury": "PHO",
}
SEASON = "2025"


def get_season_games(team_abbrev, season):
    """Pull all regular-season games for a team via LeagueGameFinder."""
    url = "https://stats.wnba.com/stats/leaguegamefinder"
    params = {
        "PlayerOrTeam": "T",
        "Season": season,
        "SeasonType": "Regular Season",
        "LeagueID": "10",  # 10 = WNBA
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    result_set = data["resultSets"][0]
    headers_list = result_set["headers"]
    rows = result_set["rowSet"]

    idx = {name: i for i, name in enumerate(headers_list)}

    games = []
    for row in rows:
        if row[idx["TEAM_ABBREVIATION"]] != team_abbrev:
            continue
        games.append({
            "game_id": row[idx["GAME_ID"]],
            "date": row[idx["GAME_DATE"]],
            "matchup": row[idx["MATCHUP"]],  # e.g. "IND vs. CHI" or "IND @ CHI"
            "result": row[idx["WL"]],
        })

    # sort chronologically
    games.sort(key=lambda g: g["date"])
    return games


def get_boxscore_availability(game_id, team_abbrev):
    """Return (available_count, entered_count, total_minutes) for the team in this game."""
    url = "https://stats.wnba.com/stats/boxscoretraditionalv2"
    params = {
        "GameID": game_id,
        "StartPeriod": 0,
        "EndPeriod": 14,
        "StartRange": 0,
        "EndRange": 2147483647,
        "RangeType": 0,
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # PlayerStats is typically resultSets[0]
    player_stats = None
    for rs in data["resultSets"]:
        if rs["name"] == "PlayerStats":
            player_stats = rs
            break
    if player_stats is None:
        raise RuntimeError(f"Could not find PlayerStats in response for game {game_id}")

    headers_list = player_stats["headers"]
    rows = player_stats["rowSet"]
    idx = {name: i for i, name in enumerate(headers_list)}

    available = 0
    entered = 0
    total_minutes = 0.0

    for row in rows:
        if row[idx["TEAM_ABBREVIATION"]] != team_abbrev:
            continue
        available += 1

        min_val = row[idx["MIN"]]
        if min_val:  # non-blank/non-null means they got in the game
            entered += 1
            # MIN is usually formatted "MM:SS" or "MM.SS" depending on endpoint version
            try:
                if ":" in str(min_val):
                    mins, secs = str(min_val).split(":")
                    total_minutes += int(mins) + int(secs) / 60
                else:
                    total_minutes += float(min_val)
            except (ValueError, TypeError):
                pass

    return available, entered, round(total_minutes, 1)


def main():
    for team_name, team_code in TEAMS.items():
        print(f"\n=== {team_name} ({team_code}) ===")
        try:
            games = get_season_games(team_code, SEASON)
        except Exception as e:
            print(f"  Failed to fetch schedule: {e}")
            continue
        print(f"Found {len(games)} games")

        rows = []
        for i, game in enumerate(games, 1):
            try:
                avail, entered, mins = get_boxscore_availability(game["game_id"], team_code)
            except Exception as e:
                print(f"  Game {i} ({game['game_id']}) failed: {e}")
                continue

            rows.append({
                "game_num": i,
                "date": game["date"],
                "matchup": game["matchup"],
                "result": game["result"],
                "available": avail,
                "entered": entered,
                "minutes": mins,
            })
            print(f"  Game {i}/{len(games)} ({game['date']}, {game['matchup']}, {game['result']}): "
                  f"Available={avail}, Entered={entered}, Minutes={mins}")

            time.sleep(DELAY_SECONDS)

        games_played = len(rows)
        if games_played:
            total_avail = sum(r["available"] for r in rows)
            total_entered = sum(r["entered"] for r in rows)
            total_minutes = sum(r["minutes"] for r in rows)
            print(f"\n{team_name} totals:")
            print(f"  Games: {games_played}")
            print(f"  Total Available: {total_avail} ({total_avail / games_played:.2f}/game)")
            print(f"  Total Entered: {total_entered} ({total_entered / games_played:.2f}/game)")
            print(f"  Total Minutes: {total_minutes:.1f} ({total_minutes / games_played:.2f}/game)")

        out_file = f"wnba_availability_{team_name.lower()}_{SEASON}.csv"
        with open(out_file, "w", newline="") as f:
            fieldnames = ["game_num", "date", "matchup", "result", "available", "entered", "minutes"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  Wrote {out_file}")


if __name__ == "__main__":
    main()
