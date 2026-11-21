"""
WNBA AGE Summary - Multi-Team (2025 Season)
---------------------------------------------
Same metrics/format as NBA_Injury_Rate_Summary_v5.pdf, computed per team
from ESPN's WNBA box score data. Loops over a list of teams and produces
one row per team in the output CSV (plus a per-team printout).

No API key required. Undocumented endpoint - if parsing breaks for a
team, print raw box score JSON for one of its games and inspect the
players[] structure.
"""

import requests
import pandas as pd
import time

# Add/remove teams here. ESPN abbreviations (lowercase, as used in the
# teams/{slug}/schedule URL).
TEAMS = {
    "gs":  "Golden State Valkyries",
    "ind": "Indiana Fever",
    "nyl": "New York Liberty",
    "lv":  "Las Vegas Aces",
    "min": "Minnesota Lynx",
    "sea": "Seattle Storm",
}

SEASON_YEAR = 2025
SEASON_TYPE = 2             # 2 = regular season, 3 = postseason
STANDARD_GAME_LENGTH = 200  # WNBA regulation: 5 players x 40 min = 200 team-minutes

SCHEDULE_URL_TMPL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{slug}/schedule"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"


def fetch_schedule(slug: str, season_year: int, season_type: int) -> list:
    url = SCHEDULE_URL_TMPL.format(slug=slug)
    resp = requests.get(url, params={"season": season_year, "seasontype": season_type}, timeout=15)
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


def game_went_to_ot(boxscore: dict) -> bool:
    """
    Real OT signal instead of the minutes-threshold proxy: WNBA regulation
    is 4 periods. If the game's period count exceeds 4, it went to OT.
    Falls back to linescores length if 'period' isn't present.
    """
    try:
        competitions = boxscore.get("header", {}).get("competitions", [])
        if competitions:
            period = competitions[0].get("status", {}).get("period")
            if period is not None:
                return period > 4
    except Exception:
        pass

    # Fallback: check a team's linescores array length (>4 entries = OT)
    for team_block in boxscore.get("boxscore", {}).get("teams", []):
        linescores = team_block.get("linescores")
        if linescores:
            return len(linescores) > 4
    return False


def game_stats(boxscore: dict, team_name: str) -> dict:
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

    went_ot = game_went_to_ot(boxscore)
    return {
        "minutes": minutes_total,
        "rostered": rostered,
        "entered": entered,
        "injuries": dnp_injury_count,
        "overtime": went_ot,
    }


def summarize_team(slug: str, team_name: str) -> dict:
    print(f"\nFetching {SEASON_YEAR} schedule for {team_name}...")
    game_ids = fetch_schedule(slug, SEASON_YEAR, SEASON_TYPE)
    n_games = len(game_ids)
    print(f"  Found {n_games} completed games.")

    totals = {"minutes": 0.0, "rostered": 0, "entered": 0, "injuries": 0, "overtime": 0}

    for i, gid in enumerate(game_ids, 1):
        print(f"  [{i}/{n_games}] game {gid}...", end="\r")
        try:
            box = fetch_boxscore(gid)
            g = game_stats(box, team_name)
            totals["minutes"] += g["minutes"]
            totals["rostered"] += g["rostered"]
            totals["entered"] += g["entered"]
            totals["injuries"] += g["injuries"]
            totals["overtime"] += int(g["overtime"])
        except Exception as e:
            print(f"\n  Failed on game {gid}: {e}")
        time.sleep(0.5)

    return {
        "Team": team_name,
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


def main():
    all_summaries = []
    for slug, team_name in TEAMS.items():
        try:
            summary = summarize_team(slug, team_name)
            all_summaries.append(summary)
        except Exception as e:
            print(f"\nFailed on team {team_name} ({slug}): {e}")

    df = pd.DataFrame(all_summaries)
    out_path = f"wnba_AGE_summary_{SEASON_YEAR}_multi_team.csv"
    df.to_csv(out_path, index=False)

    print("\n\n=== SUMMARY ===")
    print(df.to_string(index=False))
    print(f"\nSaved to {out_path}")
    print(
        "\nNote: 'overtime' is a proxy (season minutes exceeding standard game length) - "
        "same caveat as the NBA version, worth a manual spot-check. "
        "'Injuries recorded' counts DNP reasons containing an injury keyword; "
        "coach's-decision DNPs are excluded."
    )


if __name__ == "__main__":
    main()
cd ~/Downloads
python3 wnba_multi_team_age_summary.py

