"""
NBA Per-Game Roster Availability Scraper — Clippers Edition
────────────────────────────────────────────────────────────
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

Default team : LAC  (Los Angeles Clippers)
Default season: 2025  (2024-25 season)
Output file  : LAC_season_metrics_2025.csv  (saved to ~/Downloads)
"""

import re
import time
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment

# ──────────────────────────────────────────────────────────────
TEAM   = "LAC"
SEASON = 2025
DELAY  = 4          # seconds between requests — be polite to B-Ref
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Status strings that mean the player WAS dressed and eligible (→ counts for A)
DNP_DRESSED_STATUSES = {"did not play"}

# Status strings that mean the player could NOT enter (→ excluded from A)
INACTIVE_STATUSES = {
    "did not dress",
    "not with team",
    "player suspended",
    "inactive",
}
# ──────────────────────────────────────────────────────────────


def get_schedule(team: str, season: int) -> list[dict]:
    """Return list of {game_id, date, home, away, result} for all regular-season games."""
    url = f"https://www.basketball-reference.com/teams/{team}/{season}_games.html"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table", {"id": "games"})
    if table is None:
        raise RuntimeError(f"Could not find schedule table for {team} {season}")

    games = []
    for row in table.find("tbody").find_all("tr"):
        # skip header rows injected mid-table
        if row.get("class") and "thead" in row.get("class"):
            continue

        cells = {td.get("data-stat"): td for td in row.find_all(["td", "th"])}

        # Skip rows without a game link
        if "date_game" not in cells:
            continue
        a_tag = cells["date_game"].find("a")
        if a_tag is None:
            continue

        # Skip playoff games (they appear after the 82-game block; we filter by game_season)
        game_season = cells["game_season"].get_text(strip=True) if "game_season" in cells else ""

        date_str = cells["date_game"].get_text(strip=True)
        game_href = a_tag["href"]                          # e.g. /boxscores/202410220LAC.html
        game_id   = game_href.split("/")[-1].replace(".html", "")

        opp = cells.get("opp", cells.get("opp_id"))
        opp_text = opp.get_text(strip=True) if opp else "?"

        # Home/away — if there's an '@' in the game_location cell, team was away
        loc_cell  = cells.get("game_location", None)
        away_game = loc_cell is not None and "@" in loc_cell.get_text()

        result_cell = cells.get("game_result", None)
        result = result_cell.get_text(strip=True) if result_cell else ""

        games.append(
            dict(
                game_id=game_id,
                date=date_str,
                opp=opp_text,
                home_away="Away" if away_game else "Home",
                result=result,
            )
        )

    return games


def parse_boxscore_tables(soup: BeautifulSoup, team: str) -> BeautifulSoup | None:
    """
    Basketball-Reference hides some box score tables inside HTML comments.
    This extracts and parses the team-specific basic box score table.
    """
    # Table id looks like "box-LAC-game-basic"
    table_id = f"box-{team}-game-basic"

    # First try directly in the DOM
    table = soup.find("table", {"id": table_id})
    if table:
        return table

    # If not found, look inside HTML comments (B-Ref often wraps these)
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if table_id in comment:
            comment_soup = BeautifulSoup(comment, "html.parser")
            table = comment_soup.find("table", {"id": table_id})
            if table:
                return table

    return None


def get_game_metrics(game_id: str, team: str) -> dict:
    """
    Scrape one box score page and return per-game metrics.
    Returns a dict with keys: players_entered, dnp_dressed, inactive, minutes, ot.
    """
    url = f"https://www.basketball-reference.com/boxscores/{game_id}.html"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = parse_boxscore_tables(soup, team)
    if table is None:
        print(f"  [WARN] Could not find box score table for {game_id}")
        return dict(players_entered=0, dnp_dressed=0, inactive=0, minutes=0.0, ot=0)

    players_entered = 0
    dnp_dressed     = 0
    inactive        = 0
    total_minutes   = 0.0

    tbody = table.find("tbody")
    if tbody is None:
        return dict(players_entered=0, dnp_dressed=0, inactive=0, minutes=0.0, ot=0)

    for row in tbody.find_all("tr"):
        # Skip divider rows (e.g., the "Reserves" sub-header row)
        if row.get("class") and "thead" in row.get("class"):
            continue

        reason_cell = row.find("td", {"data-stat": "reason"})
        mp_cell     = row.find("td", {"data-stat": "mp"})

        if reason_cell is not None:
            # This player did NOT play — classify by the reason text
            reason_text = reason_cell.get_text(strip=True).lower()
            if any(s in reason_text for s in DNP_DRESSED_STATUSES):
                dnp_dressed += 1          # dressed, could have entered → counts for A
            elif any(s in reason_text for s in INACTIVE_STATUSES):
                inactive += 1             # could NOT enter → excluded from A
            else:
                # Unrecognised status — treat conservatively as inactive
                inactive += 1
        elif mp_cell is not None:
            # Has a minutes cell → actually played
            mp_text = mp_cell.get_text(strip=True)
            if mp_text and mp_text not in ("", "Did Not Play"):
                # Parse "MM:SS" → float minutes
                try:
                    parts = mp_text.split(":")
                    mins  = int(parts[0]) + int(parts[1]) / 60
                    total_minutes   += mins
                    players_entered += 1
                except (ValueError, IndexError):
                    pass

    # Infer overtime: regulation = 5 players × 48 min = 240.0 min
    # Each OT period adds 5 × 5 = 25 min
    ot_periods = 0
    if total_minutes > 241:                # allow tiny float rounding
        extra = total_minutes - 240.0
        ot_periods = round(extra / 25)

    return dict(
        players_entered=players_entered,
        dnp_dressed=dnp_dressed,
        inactive=inactive,
        minutes=round(total_minutes, 1),
        ot=ot_periods,
    )


def main():
    team   = TEAM
    season = SEASON

    print(f"\n{'='*60}")
    print(f"  NBA Roster Availability Scraper — {team} {season-1}-{str(season)[2:]}")
    print(f"{'='*60}")
    print(f"  Fetching schedule …")

    schedule = get_schedule(team, season)
    total    = len(schedule)
    print(f"  Found {total} games.\n")

    rows = []
    for i, game in enumerate(schedule, 1):
        gid = game["game_id"]
        print(
            f"  [{i:>2}/{total}]  {game['date']}  vs {game['opp']:>3}  ({game['home_away']})  …",
            end="",
            flush=True,
        )
        try:
            metrics = get_game_metrics(gid, team)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            metrics = dict(players_entered=0, dnp_dressed=0, inactive=0, minutes=0.0, ot=0)

        a_avail  = metrics["players_entered"] + metrics["dnp_dressed"]
        b_entered = metrics["players_entered"]

        print(f"  A={a_avail}  B={b_entered}  OT={metrics['ot']}")

        rows.append(
            {
                "Game #":           i,
                "Date":             game["date"],
                "Opp":              game["opp"],
                "Home/Away":        game["home_away"],
                "Result":           game["result"],
                "(A) Available":    a_avail,
                "(B) Entered":      b_entered,
                "DNP_dressed":      metrics["dnp_dressed"],
                "Inactive":         metrics["inactive"],
                "Minutes":          metrics["minutes"],
                "OT":               metrics["ot"],
                "(C) InGameInjury": "",   # fill manually
            }
        )

        time.sleep(DELAY)

    df = pd.DataFrame(rows)

    # ── Console summary (narrow — won't wrap in Terminal) ──────────────
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"  {team} {season-1}-{str(season)[2:]}  —  Season Summary")
    print(sep)
    console_cols = ["Game #", "Date", "Opp", "Result", "(A) Available", "(B) Entered", "OT"]
    print(df[console_cols].to_string(index=False))
    print(f"\n(Console shows key columns only — the saved CSV has all columns,")
    print(f" including (C) InGameInjury, DNP_dressed, Inactive, and Minutes.)")

    # ── Season averages ───────────────────────────────────────────────
    print(f"\n{sep}")
    print(f"  SEASON AVERAGES")
    print(sep)
    print(f"  (A) Avg available per game : {df['(A) Available'].mean():.2f}")
    print(f"  (B) Avg entered  per game  : {df['(B) Entered'].mean():.2f}")
    print(f"  OT games                   : {(df['OT'] > 0).sum()}")
    print(f"  Games scraped              : {len(df)}  /  {total}")
    print(sep)

    # ── Save CSV ──────────────────────────────────────────────────────
    import os
    downloads = os.path.expanduser("~/Downloads")
    out_name  = f"{team}_season_metrics_{season}.csv"
    out_path  = os.path.join(downloads, out_name)
    df.to_csv(out_path, index=False)
    print(f"\n  ✓  Saved → {out_path}\n")


if __name__ == "__main__":
    main()
