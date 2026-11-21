"""
NBA Per-Game Roster Availability Scraper — v4
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

  (C) IN-GAME INJURIES — left BLANK for manual entry. See note at bottom of
                   this file: box scores do not flag mid-game injuries, so this
                   column is intentionally empty for you to fill in.

Supporting columns: minutes played, OT periods, DNP-dressed count, inactive count.

Default team: GSW (Golden State Warriors), full 82-game regular season.

USAGE
  Full season (default — saves CSV):
    python3 nba_roster_scraper_v4.py
    python3 nba_roster_scraper_v4.py --team GSW --season 2025

  Fewer games (quick test):
    python3 nba_roster_scraper_v4.py --max_games 5

  Single game:
    python3 nba_roster_scraper_v4.py --game_id 202410230GSW --team GSW
"""

import argparse
import re
import sys
import time
from io import StringIO

import requests
from bs4 import BeautifulSoup, Comment

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
    m = re.match(r"^(\d+):(\d{2})$", str(mp_str).strip())
    if not m:
        return None
    return int(m.group(1)) + int(m.group(2)) / 60.0


# ── SCHEDULE ──────────────────────────────────────────────────────────────────

def get_schedule(team, season):
    """
    Return a list of dicts {date, opp, result, game_id} for the regular season,
    in chronological order. game_id is pulled straight from the box-score link,
    which is the only fully reliable way to get it (no home/away guessing).
    """
    url = f"{BASE}/teams/{team}/{season}_games.html"
    soup = get_soup(url)
    table = find_table(soup, "games")
    if table is None:
        print("ERROR: could not find the regular-season games table.")
        return []

    games = []
    body = table.find("tbody")
    for tr in body.find_all("tr"):
        if "thead" in (tr.get("class") or []):
            continue  # mid-table repeated header
        link = tr.find("td", {"data-stat": "box_score_text"})
        a = link.find("a") if link else None
        if not a or not a.get("href"):
            continue  # game not yet played / no box score
        gid = a["href"].split("/")[-1].replace(".html", "")
        date_cell = tr.find("td", {"data-stat": "date_game"})
        opp_cell = tr.find("td", {"data-stat": "opp_name"})
        res_cell = tr.find("td", {"data-stat": "game_result"})
        games.append({
            "date": date_cell.get_text(strip=True) if date_cell else "?",
            "opp": opp_cell.get_text(strip=True) if opp_cell else "?",
            "result": res_cell.get_text(strip=True) if res_cell else "?",
            "game_id": gid,
        })
    return games


# ── BOX SCORE (one game) ──────────────────────────────────────────────────────

def classify_box_rows(table):
    """
    Walk the basic box-score table for one team and classify every player row.
    Returns dict with counts + total minutes.
    """
    played = 0
    dnp_dressed = 0       # "Did Not Play"  -> eligible, counts toward A
    not_available = 0     # DND / inactive / not with team / suspended
    total_minutes = 0.0

    body = table.find("tbody")
    for tr in body.find_all("tr"):
        if "thead" in (tr.get("class") or []):
            continue  # "Starters" / "Reserves" separator rows
        name_cell = tr.find("th", {"data-stat": "player"})
        if not name_cell or not name_cell.get_text(strip=True):
            continue

        reason_cell = tr.find("td", {"data-stat": "reason"})
        if reason_cell is not None:
            reason = reason_cell.get_text(strip=True).lower()
            if reason in ELIGIBLE_DNP:
                dnp_dressed += 1
            else:
                # Anything else (Did Not Dress / Inactive / Not With Team /
                # Suspended, or an unrecognized reason) = could not enter.
                not_available += 1
            continue

        mp_cell = tr.find("td", {"data-stat": "mp"})
        mins = parse_minutes(mp_cell.get_text(strip=True)) if mp_cell else None
        if mins is not None:
            played += 1
            total_minutes += mins
        # If there's no reason and no parseable minutes, skip (defensive).

    return {
        "played": played,
        "dnp_dressed": dnp_dressed,
        "not_available": not_available,
        "total_minutes": round(total_minutes, 1),
    }


def get_game_metrics(game_id, team):
    """Fetch one box score and compute (A), (B) and supporting numbers."""
    url = f"{BASE}/boxscores/{game_id}.html"
    try:
        soup = get_soup(url)
    except Exception as e:
        print(f"    fetch failed: {e}")
        return None

    table = find_table(soup, f"box-{team}-game-basic")
    if table is None:
        # Fallback: any basic box table mentioning the team code.
        for t in soup.find_all("table"):
            tid = t.get("id", "")
            if tid.startswith("box-") and team in tid and tid.endswith("-game-basic"):
                table = t
                break
    if table is None:
        print(f"    could not find box table box-{team}-game-basic")
        return None

    c = classify_box_rows(table)
    available = c["played"] + c["dnp_dressed"]      # (A)
    entered = c["played"]                            # (B)

    # OT inference: regulation team-minutes = 240; each OT adds 25.
    ot = 0
    if c["total_minutes"] > 241:
        ot = round((c["total_minutes"] - 240) / 25)

    return {
        "(A) Available": available,
        "(B) Entered": entered,
        "DNP_dressed": c["dnp_dressed"],
        "Not_available": c["not_available"],
        "Minutes": c["total_minutes"],
        "OT": ot,
    }


# ── COMMANDS ──────────────────────────────────────────────────────────────────

def cmd_game(game_id, team):
    team = team.upper()
    print(f"\nFetching box score {game_id} ({team})...")
    m = get_game_metrics(game_id, team)
    if not m:
        print("Could not fetch. Check game_id and team code.")
        return
    ot = f"  (+{m['OT']} OT)" if m["OT"] else ""
    print(f"\n── {team} | {game_id} ──")
    print(f"  (A) Available (could enter) : {m['(A) Available']}")
    print(f"  (B) Entered (played 1s+)    : {m['(B) Entered']}")
    print(f"      DNP - dressed           : {m['DNP_dressed']}")
    print(f"      Inactive / not w/ team  : {m['Not_available']}")
    print(f"      Minutes played          : {m['Minutes']}{ot}")


def cmd_season(team, season, max_games):
    team = team.upper()
    print(f"\nFetching {team} {season} schedule...")
    sched = get_schedule(team, season)
    if not sched:
        return
    n = min(max_games, len(sched))
    print(f"  {len(sched)} games found — processing {n}")
    print(f"  (~{DELAY:.0f}s per game, so roughly {n * DELAY / 60:.1f} min total)\n")

    import pandas as pd
    rows = []
    for i, g in enumerate(sched):
        if i >= max_games:
            break
        print(f"  [{i+1}/{n}] {g['date']} vs {g['opp']} ({g['result']})  →  {g['game_id']}")
        m = get_game_metrics(g["game_id"], team)
        if not m:
            print("    skipped.")
            continue
        rows.append({
            "Game #": i + 1,
            "Date": g["date"],
            "Opp": g["opp"],
            "Result": g["result"],
            "(A) Available": m["(A) Available"],
            "(B) Entered": m["(B) Entered"],
            "(C) InGameInjuries": "",          # manual entry — see note
            "DNP_dressed": m["DNP_dressed"],
            "Inactive": m["Not_available"],
            "Minutes": m["Minutes"],
            "OT": m["OT"],
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
    print(df.to_string(index=False))

    out = f"{team}_season_metrics_{season}.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print("Fill in the (C) InGameInjuries column by hand (see note in the script header).")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="NBA per-game roster availability scraper (Basketball-Reference)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--team", default="GSW", help="3-letter team code (default: GSW)")
    p.add_argument("--season", default="2025", help="Season END year (default: 2025 = 2024-25)")
    p.add_argument("--max_games", type=int, default=82, help="Games to process (default: 82)")
    p.add_argument("--game_id", help="Single game, e.g. 202410230GSW")
    args = p.parse_args()

    if args.game_id:
        cmd_game(args.game_id, args.team)
    else:
        cmd_season(args.team, args.season, args.max_games)


if __name__ == "__main__":
    main()
