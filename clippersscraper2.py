"""
NBA Per-Game Roster Availability Scraper — Clippers Edition
------------------------------------------------------------
Source: Basketball-Reference.com (free, no API key)

Per-game metrics, one row per game across the full 82-game regular season:

  (A) AVAILABLE  -- players who COULD have entered the game.
                   = players who played  +  players listed "Did Not Play"
                     (DNP-Coach's Decision: dressed, on the bench, eligible).
                   EXCLUDES "Did Not Dress", "Inactive", "Not With Team",
                     "Player Suspended" -- those players could not enter.

  (B) ENTERED    -- players who actually got into the game, even for 1 second
                   (any minutes logged in the box score).

  (C) IN-GAME INJURIES -- left BLANK for manual entry.

Output: LAC_season_metrics_2025.csv in ~/Downloads
"""

import re
import time
import csv
import os
from datetime import datetime
from typing import Optional, List, Dict, Tuple

import requests
from bs4 import BeautifulSoup, Comment

# ── Configuration ──────────────────────────────────────────────────────────────
TEAM        = "LAC"
SEASON      = 2025
DELAY       = 4          # seconds between requests (be polite to BBref)
OUTPUT_FILE = os.path.expanduser(f"~/Downloads/{TEAM}_season_metrics_2025.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}

# Statuses that mean the player was dressed and eligible to enter
ELIGIBLE_DNP = {"did not play"}

# Statuses that mean the player could NOT enter
NOT_AVAILABLE = {"did not dress", "not with team", "player suspended", "inactive"}

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_soup(url: str) -> Optional[BeautifulSoup]:
    """Fetch a page and return a BeautifulSoup object, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [ERROR] Could not fetch {url}: {e}")
        return None


def get_season_game_ids(team: str, season: int) -> List[Dict]:
    """Return a list of dicts with game metadata from the team game log."""
    url = f"https://www.basketball-reference.com/teams/{team}/{season}/gamelog/"
    print(f"Fetching game log: {url}")
    soup = get_soup(url)
    if soup is None:
        return []

    table = soup.find("table", {"id": "tgl_basic"})
    if table is None:
        # BBref sometimes hides tables inside HTML comments — search there too
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            if "tgl_basic" in comment:
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", {"id": "tgl_basic"})
                if table:
                    break
    if table is None:
        print("  [ERROR] Could not find game log table.")
        return []

    games = []
    for row in table.find("tbody").find_all("tr"):
        # Skip header rows and blank separators
        if row.get("class") and "thead" in row.get("class"):
            continue
        rk_cell = row.find("td", {"data-stat": "ranker"})
        if rk_cell is None:
            continue
        try:
            game_num = int(rk_cell.text.strip())
        except ValueError:
            continue

        date_cell  = row.find("td", {"data-stat": "date_game"})
        opp_cell   = row.find("td", {"data-stat": "opp"})
        result_cell = row.find("td", {"data-stat": "game_result"})

        if not date_cell or not opp_cell:
            continue

        date_str = date_cell.text.strip()
        opp      = opp_cell.text.strip()
        result   = result_cell.text.strip() if result_cell else ""

        # Build box score URL from the anchor tag
        a_tag = date_cell.find("a")
        if a_tag is None:
            continue
        boxscore_url = "https://www.basketball-reference.com" + a_tag["href"]

        games.append({
            "game_num":     game_num,
            "date":         date_str,
            "opp":          opp,
            "result":       result,
            "boxscore_url": boxscore_url,
        })

    return games


def parse_boxscore_tables(soup: BeautifulSoup, team: str) -> Optional[BeautifulSoup]:
    """
    Find the team's box score table. BBref hides some tables in HTML comments;
    this searches both visible DOM and comment nodes.
    """
    table_id = f"box-{team}-game-basic"

    # Try visible DOM first
    table = soup.find("table", {"id": table_id})
    if table:
        return table

    # Search inside HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if table_id in comment:
            comment_soup = BeautifulSoup(comment, "html.parser")
            table = comment_soup.find("table", {"id": table_id})
            if table:
                return table

    return None


def classify_player_row(row) -> str:
    """
    Return one of: 'played', 'eligible_dnp', 'not_available', 'unknown'
    based on the row's reason data-stat or minutes played.
    """
    reason_cell = row.find("td", {"data-stat": "reason"})
    mp_cell     = row.find("td", {"data-stat": "mp"})

    if reason_cell:
        reason = reason_cell.text.strip().lower()
        if reason in ELIGIBLE_DNP:
            return "eligible_dnp"
        if any(na in reason for na in NOT_AVAILABLE):
            return "not_available"

    if mp_cell:
        mp_text = mp_cell.text.strip()
        if mp_text and mp_text not in ("", "Did Not Play", "Did Not Dress",
                                       "Not With Team", "Player Suspended",
                                       "Inactive"):
            # Has a time value like "32:10" — player entered the game
            return "played"

    return "unknown"


def detect_overtime(soup: BeautifulSoup, team: str) -> bool:
    """
    Infer overtime by summing team minutes. Regulation = 240 min exactly.
    Each OT period adds ~25 minutes (5 min x 5 players).
    """
    table = parse_boxscore_tables(soup, team)
    if table is None:
        return False

    total_seconds = 0
    for row in table.find("tbody").find_all("tr"):
        mp_cell = row.find("td", {"data-stat": "mp"})
        if mp_cell is None:
            continue
        mp_text = mp_cell.text.strip()
        if ":" in mp_text:
            try:
                mins, secs = mp_text.split(":")
                total_seconds += int(mins) * 60 + int(secs)
            except ValueError:
                pass

    total_minutes = total_seconds / 60
    return total_minutes > 241  # buffer for rounding


def scrape_game(game: Dict) -> Optional[Dict]:
    """Scrape a single box score and return metric dict, or None on failure."""
    url = game["boxscore_url"]
    soup = get_soup(url)
    if soup is None:
        return None

    table = parse_boxscore_tables(soup, TEAM)
    if table is None:
        print(f"  [WARN] No {TEAM} table found at {url}")
        return None

    available  = 0
    entered    = 0

    for row in table.find("tbody").find_all("tr"):
        # Skip section header rows inside tbody
        if row.get("class") and "thead" in row.get("class"):
            continue
        player_cell = row.find("td", {"data-stat": "player"})
        if player_cell is None:
            continue

        status = classify_player_row(row)
        if status == "played":
            available += 1
            entered   += 1
        elif status == "eligible_dnp":
            available += 1
        # not_available and unknown: don't count

    ot = detect_overtime(soup, TEAM)

    return {
        "game_num":         game["game_num"],
        "date":             game["date"],
        "opponent":         game["opp"],
        "result":           game["result"],
        "available_A":      available,
        "entered_B":        entered,
        "in_game_injury_C": "",         # fill in manually
        "overtime":         "OT" if ot else "",
        "boxscore_url":     game["boxscore_url"],
    }


# ── Narrow console table printer ───────────────────────────────────────────────

def print_row(g: Dict) -> None:
    print(
        f"  #{g['game_num']:>2}  {g['date']:<12}  "
        f"vs {g['opponent']:<4}  {g['result']:<6}  "
        f"A={g['available_A']:>2}  B={g['entered_B']:>2}  "
        f"{g['overtime']}"
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{'='*60}")
    print(f"  LA Clippers ({TEAM}) — {SEASON} Season Roster Metrics")
    print(f"{'='*60}\n")

    games = get_season_game_ids(TEAM, SEASON)
    if not games:
        print("No games found. Exiting.")
        return

    print(f"Found {len(games)} games. Scraping box scores...\n")
    print(f"  {'#':>2}  {'Date':<12}  {'Opp':<7}  {'Res':<6}  {'A':>3}  {'B':>3}  OT")
    print(f"  {'-'*50}")

    results = []
    for i, game in enumerate(games, 1):
        print(f"  [{i}/{len(games)}] {game['date']} vs {game['opp']} ...", end=" ", flush=True)
        metrics = scrape_game(game)
        if metrics:
            results.append(metrics)
            print(f"A={metrics['available_A']}  B={metrics['entered_B']}  {metrics['overtime']}")
            print_row(metrics)
        else:
            print("SKIPPED")

        if i < len(games):
            time.sleep(DELAY)

    # Write CSV
    fieldnames = [
        "game_num", "date", "opponent", "result",
        "available_A", "entered_B", "in_game_injury_C",
        "overtime", "boxscore_url"
    ]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'='*60}")
    print(f"  Done! {len(results)}/{len(games)} games scraped.")
    print(f"  Saved to: {OUTPUT_FILE}")

    if results:
        avg_a = sum(r["available_A"] for r in results) / len(results)
        avg_b = sum(r["entered_B"]   for r in results) / len(results)
        ot_games = sum(1 for r in results if r["overtime"] == "OT")
        print(f"\n  Season averages:")
        print(f"    Avg Available (A): {avg_a:.1f}")
        print(f"    Avg Entered   (B): {avg_b:.1f}")
        print(f"    Overtime games:    {ot_games}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
