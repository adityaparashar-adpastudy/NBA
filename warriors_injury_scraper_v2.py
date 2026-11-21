"""
Warriors (or any NBA team) Injury Log Scraper
Source: prosportstransactions.com — the standard structured archive of
NBA injury/IL transactions, searchable by team and date range.

WHAT THIS PULLS:
    Date | Team | Player | Notes (injury description / IL move)

USAGE:
    python warriors_injury_scraper.py

OUTPUT:
    warriors_injuries_2024_25.csv

NOTE ON CLOUDFLARE:
    prosportstransactions.com sits behind Cloudflare bot protection.
    A plain `requests` call will often get a 403 or a JS challenge page
    instead of the real HTML table. This script tries a plain request
    first (works for many casual scrapers with the right headers), and
    falls back to instructions for using `cloudscraper` if blocked.

    If you get blocked:
        pip install cloudscraper --break-system-packages
    and swap `requests.Session()` for `cloudscraper.create_scraper()`
    (drop-in replacement, same .get() interface — see bottom of file).
"""

import csv
import re
import time
from datetime import datetime

import cloudscraper
from bs4 import BeautifulSoup

BASE_URL = "https://www.prosportstransactions.com/basketball/Search/SearchResults.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.prosportstransactions.com/basketball/Search/",
}


def build_params(team: str, begin_date: str, end_date: str, start_row: int = 0) -> dict:
    """
    team: e.g. 'Warriors' (as spelled on the site)
    begin_date / end_date: 'YYYY-MM-DD'
    start_row: pagination offset (site returns ~25 rows per page)
    """
    return {
        "Player": "",
        "Team": team,
        "BeginDate": begin_date,
        "EndDate": end_date,
        "ILChkBx": "yes",        # include injured list moves
        "InjuriesChkBx": "yes",  # include general injury notes
        "Submit": "Search",
        "start": start_row,
    }


def parse_table(html: str):
    """Parse the results table into a list of dicts."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="datatable")
    if table is None:
        return []

    rows = table.find_all("tr")[1:]  # skip header row
    records = []
    for row in rows:
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cells) < 4:
            continue
        # Typical columns: Date | Team | Acquired | Relinquished | Notes
        date, team = cells[0], cells[1]
        acquired = cells[2] if len(cells) > 2 else ""
        relinquished = cells[3] if len(cells) > 3 else ""
        notes = cells[4] if len(cells) > 4 else ""

        # Player name is usually in "relinquished" for injuries
        player_raw = relinquished or acquired
        player = re.sub(r"^[•\s]+", "", player_raw).strip()

        records.append({
            "date": date,
            "team": team,
            "player": player,
            "notes": notes,
        })
    return records


def scrape_team_injuries(team: str, begin_date: str, end_date: str, max_pages: int = 20):
    session = cloudscraper.create_scraper()
    all_records = []

    for page in range(max_pages):
        start_row = page * 25
        params = build_params(team, begin_date, end_date, start_row)
        resp = session.get(BASE_URL, params=params, headers=HEADERS, timeout=15)

        if resp.status_code != 200 or "Just a moment" in resp.text or "cf-browser-verification" in resp.text:
            print(f"[!] Possible Cloudflare block at page {page} (status {resp.status_code}).")
            print("    Try the cloudscraper fallback described in the file header.")
            break

        records = parse_table(resp.text)
        if not records:
            break  # no more results, stop paginating

        all_records.extend(records)
        print(f"  page {page}: {len(records)} rows")
        time.sleep(1.5)  # be polite, avoid rate limiting

    return all_records


def is_in_game_injury(notes: str) -> bool:
    """
    Heuristic flag: does this entry look like an acute in-game injury
    vs. rest/DTD maintenance/illness/personal reasons?
    Adjust keyword lists as you review real data.
    """
    notes_lower = notes.lower()
    rest_terms = ["rest", "load management", "personal", "suspension", "illness", "coach's decision"]
    if any(t in notes_lower for t in rest_terms):
        return False
    injury_terms = ["strain", "sprain", "fracture", "tear", "contusion", "surgery",
                    "soreness", "spasm", "injury", "acl", "mcl", "hamstring", "ankle",
                    "knee", "back", "shoulder", "concussion"]
    return any(t in notes_lower for t in injury_terms)


def main():
    team = "Warriors"
    begin_date = "2024-10-01"
    end_date = "2025-06-30"

    print(f"Scraping {team} injury transactions {begin_date} to {end_date}...")
    records = scrape_team_injuries(team, begin_date, end_date)

    for r in records:
        r["likely_in_game_injury"] = is_in_game_injury(r["notes"])

    out_path = "warriors_injuries_2024_25.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "team", "player", "notes", "likely_in_game_injury"])
        writer.writeheader()
        writer.writerows(records)

    print(f"\nDone. {len(records)} total records written to {out_path}")
    in_game_count = sum(1 for r in records if r["likely_in_game_injury"])
    print(f"Flagged as likely in-game injuries: {in_game_count}")


if __name__ == "__main__":
    main()



