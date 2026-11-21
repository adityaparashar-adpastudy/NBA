"""
NBA Full-League Game Log Scraper (all 30 teams)
Source: basketball-reference.com — NOT behind Cloudflare like
prosportstransactions.com, so plain requests works.

WHAT THIS PULLS:
    For each team, the season's game-by-game box scores are used to
    count how many players were active (logged minutes) per game.
    That sum across the season = Athlete-Game-Exposure (AGE) for that team.

OUTPUT:
    team_age_2024_25.csv  -->  Team, SeasonEndYear, GamesFound, TotalAGE, AvgActivePerGame

USAGE:
    python3 full_loop_scraper.py

NOTES:
- Basketball-Reference rate-limits aggressively. This script sleeps
  between requests. Do not remove the delay or your IP may get
  temporarily blocked (usually 429 responses, or your IP timed out
  for ~1 hour).
- This scrapes the season's "Roster" + "Per Game" pages initially as
  a fast proxy: full per-game AGE (from box scores) requires visiting
  every single game log page, which is 82+ requests PER TEAM (2,460+
  total for the league). That's slow and likely to get you rate
  limited. This script defaults to a FAST APPROXIMATION using team
  Roster + Games Played (G) per player, summed -- which equals the
  same total (Σ games played by each player = AGE) without needing
  to hit every individual game page.
"""

import csv
import time

import requests
from bs4 import BeautifulSoup

from nba_team_codes import NBA_TEAM_CODES, team_url

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_DELAY_SECONDS = 4  # be conservative, BBRef blocks aggressive scrapers


def fetch_team_page(team_name: str, season_end_year: int) -> str:
    url = team_url(team_name, season_end_year)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print(f"  [!] {team_name}: HTTP {resp.status_code} for {url}")
        return ""
    return resp.text


def parse_roster_games_played(html: str):
    """
    Parses the 'Per Game' stats table on the team page, which lists
    each player and their 'G' (games played) for the season.
    Returns list of (player_name, games_played).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Basketball-Reference sometimes wraps tables in HTML comments;
    # this handles both direct and comment-wrapped cases.
    table = soup.find("table", id="per_game_stats")
    if table is None:
        # search inside comments
        import re
        comments = soup.find_all(string=lambda text: isinstance(text, str) and "per_game_stats" in text)
        for c in comments:
            inner_soup = BeautifulSoup(c, "html.parser")
            table = inner_soup.find("table", id="per_game_stats")
            if table:
                break

    if table is None:
        return []

    rows = table.find("tbody").find_all("tr") if table.find("tbody") else []
    results = []
    for row in rows:
        if row.get("class") and "thead" in row.get("class"):
            continue
        name_cell = row.find("td", {"data-stat": "name_display"}) or row.find("th", {"data-stat": "name_display"})
        games_cell = row.find("td", {"data-stat": "games"})
        if name_cell is None or games_cell is None:
            continue
        name = name_cell.get_text(strip=True)
        try:
            games = int(games_cell.get_text(strip=True))
        except ValueError:
            continue
        results.append((name, games))
    return results


def compute_team_age(team_name: str, season_end_year: int):
    html = fetch_team_page(team_name, season_end_year)
    if not html:
        return None

    player_games = parse_roster_games_played(html)
    if not player_games:
        print(f"  [!] {team_name}: could not find per-game stats table")
        return None

    total_age = sum(g for _, g in player_games)
    num_players = len(player_games)
    return {
        "team": team_name,
        "season_end_year": season_end_year,
        "num_players": num_players,
        "total_age": total_age,
    }


def main():
    season_end_year = 2025  # 2024-25 season
    out_rows = []

    print(f"Scraping AGE data for all 30 NBA teams, {season_end_year - 1}-{str(season_end_year)[-2:]} season...")
    for i, team_name in enumerate(NBA_TEAM_CODES.keys(), start=1):
        print(f"[{i}/30] {team_name}...")
        result = compute_team_age(team_name, season_end_year)
        if result:
            out_rows.append(result)
            print(f"    -> {result['num_players']} players, total AGE = {result['total_age']}")
        time.sleep(REQUEST_DELAY_SECONDS)

    out_path = "team_age_2024_25.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["team", "season_end_year", "num_players", "total_age"])
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"\nDone. Wrote {len(out_rows)} team rows to {out_path}")


if __name__ == "__main__":
    main()
