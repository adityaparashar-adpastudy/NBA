"""
AGE (Athlete-Game-Exposure) for all 30 NBA teams, 2024-25 season.
AGE = sum of games played (G) across every player on the team's roster.
Source: Basketball-Reference team pages (Per Game table).

Run:
    cd ~/Downloads
    source venv/bin/activate
    python3 nba_age.py

Outputs:
    nba_age_2024_25.csv         (team, code, players, age)
    NBA_Injury_Rate_Summary_30.pdf   (same layout as the v5 summary, one table per team)

Resumable: if it stops, run it again and it skips teams already saved.
Injuries: edit the INJURIES dict below, or drop an injuries.csv (columns: code,injuries)
next to this script. Then just run the script again -- it won't re-scrape, it only
rebuilds the PDF.

First time only:  pip install reportlab
"""
import csv
import os
import re
import time

import requests
from bs4 import BeautifulSoup, Comment

SEASON_END_YEAR = 2025
OUT = "nba_age_2024_25.csv"
DELAY = 4  # seconds between requests; Basketball-Reference rate-limits hard

TEAMS = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BRK",
    "Charlotte Hornets": "CHO", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHO",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}

# Values you already computed -- used as a sanity check
KNOWN = {"GSW": 946, "LAC": 900, "BOS": 864, "LAL": 848}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def fetch(url, tries=4):
    for attempt in range(tries):
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.text
        wait = 30 * (attempt + 1)
        print(f"    HTTP {r.status_code}, waiting {wait}s...")
        time.sleep(wait)
    return None


def find_table(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="per_game_stats")
    if table:
        return table
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        if 'id="per_game_stats"' in c:
            inner = BeautifulSoup(c, "html.parser")
            return inner.find("table", id="per_game_stats")
    return None


def team_age(code):
    url = f"https://www.basketball-reference.com/teams/{code}/{SEASON_END_YEAR}.html"
    html = fetch(url)
    if not html:
        return None
    table = find_table(html)
    if table is None:
        return None
    players, total = 0, 0
    for tr in table.find("tbody").find_all("tr"):
        if "thead" in (tr.get("class") or []):
            continue
        g = tr.find("td", {"data-stat": "games"}) or tr.find("td", {"data-stat": "g"})
        if g is None or not g.get_text(strip=True):
            continue
        name = tr.find("td", {"data-stat": "name_display"}) or tr.find("td", {"data-stat": "player"})
        if name and re.match(r"(Team Totals|Opponent)", name.get_text(strip=True)):
            continue
        total += int(g.get_text(strip=True))
        players += 1
    return players, total


# Injury counts you've already collected (code -> injuries). Add the rest here
# or in injuries.csv.
INJURIES = {"GSW": 15, "LAC": 7, "BOS": 26, "NYK": 13, "PHI": 37, "LAL": 12}


def load_injuries():
    inj = dict(INJURIES)
    if os.path.exists("injuries.csv"):
        with open("injuries.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("injuries", "").strip() != "":
                    inj[row["code"].strip().upper()] = int(row["injuries"])
    return inj


def build_pdf(rows, inj, path="NBA_Injury_Rate_Summary_30.pdf"):
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
    head = ParagraphStyle("H", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)

    doc = SimpleDocTemplate(path, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    story = [
        Paragraph("NBA Injury Rate Explorer", title),
        Paragraph("AGE Summary (2024-25 Season)", sub),
        Paragraph("Prepared for Dr. Stovitz - draft data summary, subject to confirmation.", note),
    ]

    for r in sorted(rows, key=lambda x: x["team"]):
        age = int(r["age"])
        code = r["code"]
        games = 82
        data = [
            ["Metric", "Value"],
            ["Regular season games", str(games)],
            ["Standard game length", "240 minutes"],
            ["Players entered individual games (AGE)", str(age)],
            ["Players entered per game (avg.)", f"{age / games:.2f}"],
        ]
        if code in inj:
            data.append(["Injuries", str(inj[code])])
            data.append(["Injury rate (per 1,000 AGE)", f"{inj[code] / age * 1000:.2f}"])
        else:
            data.append(["Injuries", "-"])
            data.append(["Injury rate (per 1,000 AGE)", "-"])
        t = Table(data, colWidths=[3.6 * inch, 2.6 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(KeepTogether([Paragraph(r["team"], head), t]))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Note: AGE here is the sum of games played by every player on the team's roster "
        "(Basketball-Reference season Per Game table). Game-level metrics (minutes, overtime, "
        "Available vs. Entered per game) are not included in this 30-team version.", note))
    doc.build(story)
    print(f"PDF written to {path}")


def main():
    done = {}
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done[row["code"]] = row

    rows = list(done.values())
    for i, (team, code) in enumerate(TEAMS.items(), start=1):
        if code in done:
            print(f"[{i}/30] {team}: already saved, skipping")
            continue
        print(f"[{i}/30] {team}...")
        res = team_age(code)
        if res is None:
            print("    FAILED -- run the script again later to retry")
            continue
        players, age = res
        flag = ""
        if code in KNOWN and KNOWN[code] != age:
            flag = f"  <-- MISMATCH (expected {KNOWN[code]})"
        print(f"    {players} players, AGE = {age}{flag}")
        rows.append({"team": team, "code": code, "players": players, "age": age})
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["team", "code", "players", "age"])
            w.writeheader()
            w.writerows(rows)
        time.sleep(DELAY)

    print(f"\nDone. {len(rows)}/30 teams saved to {OUT}")
    build_pdf(rows, load_injuries())


if __name__ == "__main__":
    main()
