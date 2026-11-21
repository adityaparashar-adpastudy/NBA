"""
NBA Roster Availability Scraper - Knicks, 2024-25 regular season
Outputs columns matching the tracking sheet:
  Game #, Date, Opp, Result, (A) Available, (B) Entered, (C) InGameInjury,
  DNP_dressed, Inactive, Minutes, OT

Column definitions:
  Game #        - sequential regular-season game number
  Date          - game date, pulled from the schedule page
  Opp           - opponent, pulled from the schedule page
  Result        - W/L, pulled from the schedule page
  (A) Available - players dressed and eligible to play (excludes
                  "Did Not Dress", "Not With Team", "Player Suspended";
                  INCLUDES "Inactive" and "Did Not Play"/DNP-Coach's Decision)
  (B) Entered   - subset of Available who actually recorded minutes (MP > 0)
  (C) InGameInjury - NOT reliably derivable from box score data alone; left
                  blank. Basketball-Reference's `reason` field only reflects
                  PRE-game status, not injuries that occurred mid-game. This
                  would require manual review of game recaps or the
                  play-by-play table (which flags exits but not why).
  DNP_dressed   - count of players with reason = "Did Not Play"
                  (DNP-Coach's Decision, dressed but did not play)
  Inactive      - count of players with reason = "Inactive"
  Minutes       - total team minutes played, summed across all "Entered" rows
  OT            - number of overtime periods (0 if none), from the line score

NOTE: DNP_dressed and Inactive are reported separately here (unlike the prior
version, which only used them to decide inclusion/exclusion). Both are now
counted as part of (A) Available, per your instruction.

NOTE: doesn't distinguish DNP-Coach's Decision from DNP-injury; both show as
"Did Not Play" on Basketball-Reference box scores. If you need that split,
it has to come from injury reports, not the box score.

Requires: requests, beautifulsoup4
Run from your venv: source ~/Downloads/venv/bin/activate
"""

import requests
from bs4 import BeautifulSoup
import time
import csv
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (research script; contact: you@example.com)"}
DELAY_SECONDS = 4  # be polite to basketball-reference

TEAMS = {
    "Knicks": "NYK",
}
SEASON = 2025  # 2024-25 season page suffix


def find_table(soup, table_id):
    """Find a table by id, checking HTML comments if it's not directly present."""
    table = soup.find("table", {"id": table_id})
    if table is not None:
        return table
    comments = soup.find_all(string=lambda text: isinstance(text, str) and "<!--" in text)
    for c in comments:
        if table_id in c:
            inner_soup = BeautifulSoup(c, "html.parser")
            table = inner_soup.find("table", {"id": table_id})
            if table:
                return table
    return None


def get_schedule_rows(team_code, season):
    """Fetch the team's schedule page and pull date/opp/result/box-score-url per game."""
    url = f"https://www.basketball-reference.com/teams/{team_code}/{season}_games.html"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", {"id": "games"})
    if table is None:
        raise RuntimeError(f"Could not find games table for {team_code} {season}")

    games = []
    for row in table.find("tbody").find_all("tr"):
        if row.get("class") and "thead" in row.get("class"):
            continue

        link_cell = row.find("td", {"data-stat": "box_score_text"})
        if link_cell is None:
            continue
        a = link_cell.find("a")
        if a is None:
            continue
        box_url = "https://www.basketball-reference.com" + a["href"]

        date_cell = row.find("td", {"data-stat": "date_game"})
        opp_cell = row.find("td", {"data-stat": "opp_name_abbr"}) or row.find("td", {"data-stat": "opp_name"})
        result_cell = row.find("td", {"data-stat": "game_result"})

        games.append({
            "url": box_url,
            "date": date_cell.get_text(strip=True) if date_cell else "",
            "opp": opp_cell.get_text(strip=True) if opp_cell else "",
            "result": result_cell.get_text(strip=True) if result_cell else "",
        })
    return games


def get_ot_periods(soup):
    """Determine number of OT periods from the line score table (4 quarters is regulation)."""
    line_table = find_table(soup, "line-score")
    if line_table is None:
        return 0
    header_row = line_table.find("thead")
    if header_row is None:
        return 0
    header_cells = header_row.find_all("th")
    # Count columns that look like quarter/OT labels (1,2,3,4,OT,OT2,...)
    period_labels = [c.get_text(strip=True) for c in header_cells]
    ot_count = sum(1 for label in period_labels if "OT" in label)
    return ot_count


def parse_boxscore(url, team_code):
    """Return dict with available/entered/dnp/inactive/minutes/ot for the given team."""
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table_id = f"box-{team_code}-game-basic"
    table = find_table(soup, table_id)
    if table is None:
        raise RuntimeError(f"Could not find {table_id} in {url}")

    excluded_reasons = {"Did Not Dress", "Not With Team", "Player Suspended"}

    available_count = 0
    entered_count = 0
    dnp_dressed_count = 0
    inactive_count = 0
    total_minutes = 0.0

    tbody = table.find("tbody")
    for row in tbody.find_all("tr"):
        if row.get("class") and "thead" in row.get("class"):
            continue

        reason_cell = row.find("td", {"data-stat": "reason"})
        reason_text = reason_cell.get_text(strip=True) if reason_cell else ""

        if reason_text in excluded_reasons:
            continue  # not available - skip entirely

        available_count += 1

        if reason_text == "Did Not Play":
            dnp_dressed_count += 1
        elif reason_text == "Inactive":
            inactive_count += 1

        mp_cell = row.find("td", {"data-stat": "mp"})
        mp_minutes = 0.0
        if mp_cell is not None:
            mp_text = mp_cell.get_text(strip=True)
            if mp_text and ":" in mp_text:
                mins, secs = mp_text.split(":")
                mp_minutes = int(mins) + int(secs) / 60
            elif mp_text:
                try:
                    mp_minutes = float(mp_text)
                except ValueError:
                    mp_minutes = 0.0

        if mp_minutes > 0:
            entered_count += 1
            total_minutes += mp_minutes

    ot_periods = get_ot_periods(soup)

    return {
        "available": available_count,
        "entered": entered_count,
        "dnp_dressed": dnp_dressed_count,
        "inactive": inactive_count,
        "minutes": round(total_minutes, 1),
        "ot": ot_periods,
    }


def main():
    for team_name, team_code in TEAMS.items():
        print(f"\n=== {team_name} ({team_code}) ===")
        games = get_schedule_rows(team_code, SEASON)
        print(f"Found {len(games)} games")

        rows = []

        for i, game in enumerate(games, 1):
            try:
                stats = parse_boxscore(game["url"], team_code)
            except Exception as e:
                print(f"  Game {i} ({game['url']}) failed: {e}")
                continue

            rows.append({
                "game_num": i,
                "date": game["date"],
                "opp": game["opp"],
                "result": game["result"],
                "available": stats["available"],
                "entered": stats["entered"],
                "in_game_injury": "",  # not derivable from box score - manual entry
                "dnp_dressed": stats["dnp_dressed"],
                "inactive": stats["inactive"],
                "minutes": stats["minutes"],
                "ot": stats["ot"],
            })

            print(f"  Game {i}/{len(games)} ({game['date']} vs {game['opp']}, {game['result']}): "
                  f"Available={stats['available']}, Entered={stats['entered']}, "
                  f"DNP={stats['dnp_dressed']}, Inactive={stats['inactive']}, "
                  f"Minutes={stats['minutes']}, OT={stats['ot']}")

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

        out_file = f"roster_availability_{team_name.lower()}_{SEASON}.csv"
        with open(out_file, "w", newline="") as f:
            fieldnames = ["game_num", "date", "opp", "result", "available", "entered",
                          "in_game_injury", "dnp_dressed", "inactive", "minutes", "ot"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  Wrote {out_file}")


if __name__ == "__main__":
    main()
