"""
NBA Per-Game Roster Availability Scraper — v4  (LA Clippers edition)
─────────────────────────────────────────────
Source: Basketball-Reference.com (free, no API key)

Per-game metrics, one row per game across the full 82-game regular season:

  (A) AVAILABLE  — players who COULD have entered the game.
                   = players who played  +  players listed "Did Not Play"
                     (DNP–Coach's Decision: dressed, on the bench, eligible).
                   EXCLUDES "Did Not Dress", "Inactive", "Not With Team",
                     "Player Suspended" — those players could not enter.

  (B) ENTERED    — players who actually got into the game, even for 1 second
                   (any minutes logged in the box score).

  (C) IN-GAME INJURIES — left BLANK for manual entry.

Supporting columns: minutes played, OT periods, DNP-dressed count, inactive count.

Default team: LAC (LA Clippers), full 82-game regular season, 2024-25.

USAGE
  Full season (default — saves CSV to your Downloads folder):
    python3 nba_roster_scraper_v4_LAC.py
    python3 nba_roster_scraper_v4_LAC.py --team LAC --season 2025

  Fewer games (quick test):
    python3 nba_roster_scraper_v4_LAC.py --max_games 5

  Single game:
    python3 nba_roster_scraper_v4_LAC.py --game_id 202410220LAC --team LAC

  Different team (override):
    python3 nba_roster_scraper_v4_LAC.py --team BOS --season 2025
"""

import argparse
import re
import sys
import time
from io import StringIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Comment
import pandas as pd

BASE = "https://www.basketball-reference.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
DELAY = 4.0  # seconds between requests — Basketball-Reference rate-limits hard.

# Reasons that mean the player was DRESSED and ELIGIBLE to enter (counts toward A).
ELIGIBLE_DNP = {"did not play"}
# Reasons that mean the player COULD NOT enter (excluded from A).
NOT_AVAILABLE = {
    "did not dress",
    "not with team",
    "player suspended",
    "inactive",
}


# ── HTTP ────────────────────────────────────────────────────────────────────

def get_soup(url):
    """Fetch a page (with polite delay) and return a BeautifulSoup tree."""
    time.sleep(DELAY)
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def find_table(soup, table_id):
    """Find a table by id, including tables hidden inside HTML comments."""
    t = soup.find("table", id=table_id)
    if t:
        return t
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        if table_id in c:
            t = BeautifulSoup(c, "lxml").find("table", id=table_id)
            if t:
                return t
    return None


def parse_minutes(mp_str):
    """'MM:SS' -> float minutes. Returns None if not a real time."""
    if not mp_str or ":" not in mp_str:
        return None
    try:
        m, s = mp_str.strip().split(":")
        return int(m) + int(s) / 60
    except ValueError:
        return None


# ── BOX-SCORE PARSER ────────────────────────────────────────────────────────

def parse_box(soup, team):
    """
    Returns dict:
        (A) Available  : int
        (B) Entered    : int
        DNP_dressed    : int   (eligible DNPs — included in A but not B)
        Not_available  : int   (did not dress / inactive / not with team)
        Minutes        : float (total team minutes — used for OT detection)
        OT             : int   (0 = regulation, 1+ = overtime periods)
    """
    table_id = f"box-{team}-game-basic"
    tbl = find_table(soup, table_id)
    if tbl is None:
        return None

    entered = 0
    dnp_dressed = 0
    not_available = 0
    total_minutes = 0.0

    for row in tbl.find_all("tr"):
        # Skip header / separator rows
        th = row.find("th", {"data-stat": "player"})
        if th is None:
            continue
        if th.get("class") and "thead" in th.get("class"):
            continue

        reason_cell = row.find("td", {"data-stat": "reason"})
        mp_cell = row.find("td", {"data-stat": "mp"})

        if reason_cell is not None:
            reason = reason_cell.get_text(strip=True).lower()
            if any(r in reason for r in NOT_AVAILABLE):
                not_available += 1
            else:
                # DNP–Coach's Decision or similar eligible DNP
                dnp_dressed += 1
        elif mp_cell is not None:
            mins = parse_minutes(mp_cell.get_text(strip=True))
            if mins is not None:
                entered += 1
                total_minutes += mins

    # OT: regulation = 5 players × 48 min = 240.0; each OT adds ~25 min
    ot = max(0, round((total_minutes - 240.0) / 25))

    return {
        "(A) Available": entered + dnp_dressed,
        "(B) Entered":   entered,
        "DNP_dressed":   dnp_dressed,
        "Not_available": not_available,
        "Minutes":       round(total_minutes, 1),
        "OT":            ot,
    }


# ── SCHEDULE SCRAPER ────────────────────────────────────────────────────────

def get_schedule(team, season):
    """
    Return list of dicts: {date, opp, result, box_url}
    Only regular-season games with a box score link.
    """
    url = f"{BASE}/teams/{team}/{season}_games.html"
    print(f"Fetching schedule: {url}")
    soup = get_soup(url)

    tbl = find_table(soup, "games")
    if tbl is None:
        sys.exit(f"ERROR: couldn't find schedule table for {team} {season}.")

    games = []
    for row in tbl.find_all("tr"):
        # Skip header rows
        if row.find("th", {"data-stat": "ranker", "class": "over_header"}):
            continue
        game_cell = row.find("td", {"data-stat": "game_season"})
        if game_cell is None:
            continue

        date_cell  = row.find("td", {"data-stat": "date_game"})
        opp_cell   = row.find("td", {"data-stat": "opp"})
        result_cell= row.find("td", {"data-stat": "game_result"})
        box_cell   = row.find("td", {"data-stat": "box_score_text"})

        if not box_cell:
            continue
        a = box_cell.find("a")
        if not a:
            continue  # game not yet played

        games.append({
            "date":    date_cell.get_text(strip=True) if date_cell else "",
            "opp":     opp_cell.get_text(strip=True)  if opp_cell  else "",
            "result":  result_cell.get_text(strip=True) if result_cell else "",
            "box_url": BASE + a["href"],
        })

    return games


# ── SINGLE-GAME COMMAND ──────────────────────────────────────────────────────

def cmd_game(game_id, team):
    url = f"{BASE}/boxscores/{game_id}.html"
    print(f"Fetching: {url}")
    soup = get_soup(url)
    m = parse_box(soup, team)
    if m:
        for k, v in m.items():
            print(f"  {k}: {v}")
    else:
        print("Could not parse box score.")


# ── FULL-SEASON COMMAND ──────────────────────────────────────────────────────

def cmd_season(team, season, max_games):
    games = get_schedule(team, season)
    print(f"Found {len(games)} completed games. Processing up to {max_games}...\n")

    rows = []
    for i, g in enumerate(games[:max_games]):
        print(f"  Game {i+1:3d}/{min(max_games, len(games))}  {g['date']}  vs {g['opp']:<4s}  {g['result']}  ...", end=" ", flush=True)
        try:
            soup = get_soup(g["box_url"])
            m = parse_box(soup, team)
        except Exception as e:
            print(f"SKIP ({e})")
            continue

        if m is None:
            print("SKIP (box parse failed)")
            continue

        print(f"A={m['(A) Available']}  B={m['(B) Entered']}  OT={m['OT']}")

        rows.append({
            "Game #":           i + 1,
            "Date":             g["date"],
            "Opp":              g["opp"],
            "Result":           g["result"],
            "(A) Available":    m["(A) Available"],
            "(B) Entered":      m["(B) Entered"],
            "(C) InGameInjuries": "",   # fill in manually
            "DNP_dressed":      m["DNP_dressed"],
            "Inactive":         m["Not_available"],
            "Minutes":          m["Minutes"],
            "OT":               m["OT"],
        })

    if not rows:
        print("No data collected.")
        return

    df = pd.DataFrame(rows)
    sep = "=" * 96
    print(f"\n{sep}")
    print(f"  {team} — {season} season  |  {len(df)} games")
    print(f"  Avg (A) Available per game : {df['(A) Available'].mean():.1f}")
    print(f"  Avg (B) Entered  per game  : {df['(B) Entered'].mean():.1f}")
    print(sep)

    # Narrow console table — key columns only
    display_cols = ["Game #", "Date", "Opp", "Result", "(A) Available", "(B) Entered", "OT"]
    print(df[display_cols].to_string(index=False))

    # Save full CSV to Downloads
    downloads = Path.home() / "Downloads"
    downloads.mkdir(exist_ok=True)
    out = downloads / f"{team}_season_metrics_{season}.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved full CSV: {out}")
    print("Fill in the (C) InGameInjuries column by hand.")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="NBA per-game roster availability scraper (Basketball-Reference)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--team",      default="LAC",  help="3-letter team code (default: LAC)")
    p.add_argument("--season",    default="2025", help="Season END year (default: 2025 = 2024-25)")
    p.add_argument("--max_games", type=int, default=82, help="Games to process (default: 82)")
    p.add_argument("--game_id",   help="Single game, e.g. 202410220LAC")
    args = p.parse_args()

    if args.game_id:
        cmd_game(args.game_id, args.team)
    else:
        cmd_season(args.team, args.season, args.max_games)


if __name__ == "__main__":
    main()
