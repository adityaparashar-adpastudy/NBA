"""
Fourteen-team version of the scraper that produced your Celtics / Lakers / Knicks / 76ers CSVs
(same code as ten_teams.py, just pointed at the remaining 14 NBA teams).

Same logic: team schedule page -> each box score -> Available / Entered / DNP / Inactive / Minutes.
Same definitions: Available = everyone except "Did Not Dress", "Not With Team", "Player Suspended"
(Inactive and Did Not Play count as Available). Entered = recorded any minutes.

  - OT comes from the schedule page's OT column, with the line_score table as a backup
    (Basketball-Reference hides that table inside an HTML comment)
  - Skips a team whose CSV already exists, so if it stops you can just run it again
  - Retries on rate-limit errors instead of crashing the game
  - At the end it builds NBA_Injury_Rate_Summary_14.pdf in the v5 layout (no injury row)

Run:
    cd ~/Downloads
    source venv/bin/activate
    pip install reportlab      (first time only)
    python fourteen_teams.py

Runtime: about 80 minutes (14 teams x 82 games x 4 seconds, plus request time).
Outputs: roster_availability_<team>_2025.csv for each team, plus the PDF.
"""

import csv
import os
import re
import time

import requests
from bs4 import BeautifulSoup, Comment

HEADERS = {"User-Agent": "Mozilla/5.0 (research script; contact: you@example.com)"}
DELAY_SECONDS = 4  # be polite to basketball-reference

TEAMS = {
    "Hawks": "ATL",
    "Nets": "BRK",
    "Hornets": "CHO",
    "Bulls": "CHI",
    "Pistons": "DET",
    "Magic": "ORL",
    "Raptors": "TOR",
    "Wizards": "WAS",
    "Grizzlies": "MEM",
    "Pelicans": "NOP",
    "Spurs": "SAS",
    "Jazz": "UTA",
    "Blazers": "POR",
    "Kings": "SAC",
}
FULL_NAMES = {
    "Hawks": "Atlanta Hawks", "Nets": "Brooklyn Nets", "Hornets": "Charlotte Hornets",
    "Bulls": "Chicago Bulls", "Pistons": "Detroit Pistons", "Magic": "Orlando Magic",
    "Raptors": "Toronto Raptors", "Wizards": "Washington Wizards", "Grizzlies": "Memphis Grizzlies",
    "Pelicans": "New Orleans Pelicans", "Spurs": "San Antonio Spurs", "Jazz": "Utah Jazz",
    "Blazers": "Portland Trail Blazers", "Kings": "Sacramento Kings",
}
SEASON = 2025  # 2024-25 season page suffix
PDF_OUT = "NBA_Injury_Rate_Summary_14.pdf"


def get(url, tries=5):
    for attempt in range(tries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f"    network error ({e}); retrying...")
            time.sleep(15)
            continue
        if resp.status_code == 200:
            return resp
        wait = 30 * (attempt + 1)
        print(f"    HTTP {resp.status_code}, waiting {wait}s...")
        time.sleep(wait)
    raise RuntimeError(f"could not fetch {url}")


def find_table(soup, table_id):
    """Find a table by id, checking HTML comments if it's not directly present."""
    table = soup.find("table", {"id": table_id})
    if table is not None:
        return table
    for c in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if table_id in c:
            inner_soup = BeautifulSoup(c, "html.parser")
            table = inner_soup.find("table", {"id": table_id})
            if table:
                return table
    return None


def ot_from_text(text):
    """'' -> 0, 'OT' -> 1, '2OT' -> 2, '3OT' -> 3"""
    text = text.strip().upper()
    if not text:
        return 0
    m = re.match(r"(\d*)OT", text)
    if not m:
        return 0
    return int(m.group(1)) if m.group(1) else 1


def get_schedule_rows(team_code, season):
    """Fetch the team's schedule page and pull date/opp/result/OT/box-score-url per game."""
    url = f"https://www.basketball-reference.com/teams/{team_code}/{season}_games.html"
    soup = BeautifulSoup(get(url).text, "html.parser")

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
        ot_cell = row.find("td", {"data-stat": "overtimes"})

        games.append({
            "url": box_url,
            "date": date_cell.get_text(strip=True) if date_cell else "",
            "opp": opp_cell.get_text(strip=True) if opp_cell else "",
            "result": result_cell.get_text(strip=True) if result_cell else "",
            "ot": ot_from_text(ot_cell.get_text(strip=True)) if ot_cell else None,
        })
    return games


def get_ot_periods(soup):
    """Fallback OT count from the line score table (id is 'line_score')."""
    line_table = find_table(soup, "line_score") or find_table(soup, "line-score")
    if line_table is None:
        return 0
    header_row = line_table.find("thead")
    if header_row is None:
        return 0
    labels = [c.get_text(strip=True) for c in header_row.find_all("th")]
    return sum(1 for label in labels if "OT" in label)


def parse_boxscore(url, team_code):
    """Return dict with available/entered/dnp/inactive/minutes/ot for the given team."""
    soup = BeautifulSoup(get(url).text, "html.parser")

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

    return {
        "available": available_count,
        "entered": entered_count,
        "dnp_dressed": dnp_dressed_count,
        "inactive": inactive_count,
        "minutes": round(total_minutes, 1),
        "ot": get_ot_periods(soup),
    }


FIELDS = ["game_num", "date", "opp", "result", "available", "entered",
          "in_game_injury", "dnp_dressed", "inactive", "minutes", "ot"]


def scrape_team(team_name, team_code):
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
        ot = game["ot"] if game["ot"] is not None else stats["ot"]
        rows.append({
            "game_num": i, "date": game["date"], "opp": game["opp"], "result": game["result"],
            "available": stats["available"], "entered": stats["entered"], "in_game_injury": "",
            "dnp_dressed": stats["dnp_dressed"], "inactive": stats["inactive"],
            "minutes": stats["minutes"], "ot": ot,
        })
        print(f"  Game {i}/{len(games)} ({game['date']} vs {game['opp']}, {game['result']}): "
              f"Available={stats['available']}, Entered={stats['entered']}, "
              f"Minutes={stats['minutes']}, OT={ot}")
        time.sleep(DELAY_SECONDS)

    out_file = f"roster_availability_{team_name.lower()}_{SEASON}.csv"
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {out_file} ({len(rows)} games)")


def summarize(team_name):
    path = f"roster_availability_{team_name.lower()}_{SEASON}.csv"
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return {
        "team": FULL_NAMES[team_name],
        "games": len(rows),
        "ot": sum(1 for r in rows if int(r["ot"]) > 0),
        "minutes": round(sum(float(r["minutes"]) for r in rows), 1),
        "avail": sum(int(r["available"]) for r in rows),
        "entered": sum(int(r["entered"]) for r in rows),
    }


def build_pdf(summaries):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=styles["Title"], fontSize=18, spaceAfter=4)
    sub = ParagraphStyle("S", parent=styles["Normal"], fontSize=11,
                         textColor=colors.HexColor("#444444"), spaceAfter=2)
    note = ParagraphStyle("N", parent=styles["Normal"], fontSize=9,
                          textColor=colors.HexColor("#666666"), spaceAfter=10)
    head = ParagraphStyle("H", parent=styles["Heading2"], spaceBefore=16, spaceAfter=6)

    doc = SimpleDocTemplate(PDF_OUT, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    story = [
        Paragraph("NBA Injury Rate Explorer", title),
        Paragraph("AGE Summary (2024-25 Season)", sub),
        Paragraph("Prepared for Dr. Stovitz - draft data summary, subject to confirmation.", note),
    ]
    for r in summaries:
        g = r["games"]
        data = [
            ["Metric", "Value"],
            ["Regular season games", str(g)],
            ["Standard game length", "240 minutes"],
            ["Games that went to overtime", str(r["ot"])],
            ["Total minutes played (season)", f"{r['minutes']:,.1f} minutes"],
            ["Minutes per game (avg.)", f"{r['minutes'] / g:.2f} minutes/game"],
            ["Total players rostered (season)", str(r["avail"])],
            ["Players rostered per game (avg.)", f"{r['avail'] / g:.2f}"],
            ["Players entered individual games (AGE)", str(r["entered"])],
            ["Players entered per game (avg.)", f"{r['entered'] / g:.2f}"],
        ]
        t = Table(data, colWidths=[3.6 * inch, 2.6 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        story.append(KeepTogether([Paragraph(r["team"], head), t]))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        'Note: Injury counts are excluded from this version. "Total players rostered" here reflects '
        "the game-day active/dressed roster (Available), not the full season roster or the "
        "official inactive list.", note))
    doc.build(story)
    print(f"PDF written to {PDF_OUT}")


def main():
    for team_name, team_code in TEAMS.items():
        out_file = f"roster_availability_{team_name.lower()}_{SEASON}.csv"
        if os.path.exists(out_file):
            print(f"{team_name}: {out_file} already exists, skipping")
            continue
        scrape_team(team_name, team_code)

    summaries = [summarize(t) for t in TEAMS if
                 os.path.exists(f"roster_availability_{t.lower()}_{SEASON}.csv")]
    for s in summaries:
        if s["games"] != 82:
            print(f"WARNING: {s['team']} has {s['games']} games (expected 82) - "
                  f"delete its CSV and rerun to retry")
    build_pdf(summaries)


if __name__ == "__main__":
    main()
