"""
NBA 2024-25 regular season -- same metrics as NBA_Injury_Rate_Summary_v5.pdf
(games, overtime games, total minutes, Available, Entered/AGE), injuries left out.
Currently set to TEN teams (see TARGETS below); change that list to do other teams.

Source: Basketball-Reference (schedule pages + one box score per game involving a target team).
Each box score covers BOTH teams. Ten teams is roughly 700 box scores, about 50 minutes.
It saves after every game. If it stops, run it again and it picks up where it left off.

Definitions (same as your earlier scrapers):
  Available = dressed/eligible: played, "Did Not Play", or "Inactive".
              Excludes "Did Not Dress", "Not With Team", "Player Suspended".
  Entered   = any player with a minutes entry (even seconds) -> AGE.
  Overtime  = taken from the schedule page's OT column (not guessed from minutes).

Run:
    cd ~/Downloads
    source venv/bin/activate
    pip install reportlab        (first time only)
    python3 nba_games.py

Outputs:
    nba_games_2024_25.csv            one row per team per game (the saved progress)
    nba_team_summary_2024_25.csv     one row per team
    NBA_Injury_Rate_Summary_10.pdf   v5 layout, one table per team

Injuries (optional, later): make injuries.csv next to this script with columns
code,injuries  (e.g. MIA,19). Run the script again; it won't re-scrape, it just
rebuilds the PDF with an "Injuries recorded" row for those teams.
"""
import csv
import os
import re
import time
from collections import defaultdict

import requests
from bs4 import BeautifulSoup, Comment

SEASON_END_YEAR = 2025
LAST_REG_DATE = "20250413"  # last regular-season day of 2024-25
MONTHS = ["october", "november", "december", "january", "february", "march", "april"]
DELAY = 4  # seconds between requests (Basketball-Reference rate-limits hard)

SCHEDULE_CSV = "nba_schedule_v2_2024_25.csv"
GAMES_CSV = "nba_games_2024_25.csv"
SUMMARY_CSV = "nba_team_summary_2024_25.csv"
PDF_OUT = "NBA_Injury_Rate_Summary_10.pdf"

# The ten teams to do this run (the six already in v5 -- GSW, LAC, BOS, NYK, PHI, LAL -- are excluded)
TARGETS = {"MIN", "MIA", "DEN", "OKC", "CLE", "HOU", "DAL", "MIL", "PHO", "IND"}

TEAMS = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BRK": "Brooklyn Nets",
    "CHO": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHO": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}

# From your v5 PDF -- used as a sanity check: code -> (Available, Entered/AGE)
KNOWN = {"GSW": (1070, 946), "LAC": (1064, 900), "BOS": (1053, 864),
         "NYK": (1061, 824), "PHI": (931, 832), "LAL": (1029, 848)}

NAME_TO_CODE = {name: code for code, name in TEAMS.items()}
NAME_TO_CODE["Los Angeles Clippers"] = "LAC"


def involves_target(gid, visitor, home):
    home_code = re.search(r"0([A-Z]{3})$", gid).group(1)
    return (home_code in TARGETS or NAME_TO_CODE.get(visitor) in TARGETS
            or NAME_TO_CODE.get(home) in TARGETS)


NOT_AVAILABLE = ("did not dress", "not with team", "player suspended")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def fetch(url, tries=5):
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f"    network error ({e}); retrying...")
            time.sleep(15)
            continue
        if r.status_code == 200:
            return r.text
        wait = 30 * (attempt + 1)
        print(f"    HTTP {r.status_code}, waiting {wait}s...")
        time.sleep(wait)
    return None


# ---------------------------------------------------------------- schedule
def parse_schedule(html):
    """Return [(game_id, ot_text, visitor_name, home_name)] for regular-season games on one page."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="schedule")
    games = []
    if table is None:
        return games
    for tr in table.find("tbody").find_all("tr"):
        cell = tr.find("td", {"data-stat": "box_score_text"})
        link = cell.find("a") if cell else None
        if link is None:
            continue
        m = re.search(r"/boxscores/(\d{8})0([A-Z]{3})\.html", link["href"])
        if not m or m.group(1) > LAST_REG_DATE:
            continue
        remarks = tr.find("td", {"data-stat": "game_remarks"})
        remarks = remarks.get_text(strip=True) if remarks else ""
        # NBA Cup semifinals/final don't count toward the 82
        if "Cup" in remarks and ("Semifinal" in remarks or "Final" in remarks):
            continue
        ot = tr.find("td", {"data-stat": "overtimes"})
        vis = tr.find("td", {"data-stat": "visitor_team_name"})
        home = tr.find("td", {"data-stat": "home_team_name"})
        games.append((link["href"].split("/")[-1].replace(".html", ""),
                      ot.get_text(strip=True) if ot else "",
                      vis.get_text(strip=True) if vis else "",
                      home.get_text(strip=True) if home else ""))
    return games


def load_schedule():
    if os.path.exists(SCHEDULE_CSV):
        with open(SCHEDULE_CSV, newline="", encoding="utf-8") as f:
            return [(r["game_id"], r["ot"], r["visitor"], r["home"]) for r in csv.DictReader(f)]
    games = []
    for month in MONTHS:
        url = f"https://www.basketball-reference.com/leagues/NBA_{SEASON_END_YEAR}_games-{month}.html"
        print(f"Schedule: {month}...")
        html = fetch(url)
        if html is None:
            raise SystemExit(f"Could not load {month} schedule. Run again later.")
        found = parse_schedule(html)
        print(f"    {len(found)} games")
        games += found
        time.sleep(DELAY)
    with open(SCHEDULE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["game_id", "ot", "visitor", "home"])
        w.writerows(games)
    print(f"Schedule saved: {len(games)} games (expect 1,230)\n")
    return games


# ---------------------------------------------------------------- box score
def parse_box(html):
    """Return {team_code: (available, entered, seconds)} for both teams in a box score."""
    soup = BeautifulSoup(html, "html.parser")
    pat = re.compile(r"^box-[A-Z]{3}-game-basic$")
    tables = {t["id"]: t for t in soup.find_all("table", id=pat)}
    if len(tables) < 2:
        for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
            if "-game-basic" in c:
                for t in BeautifulSoup(c, "html.parser").find_all("table", id=pat):
                    tables.setdefault(t["id"], t)
    out = {}
    for tid, table in tables.items():
        code = tid.split("-")[1]
        avail = entered = secs = 0
        for tr in table.find("tbody").find_all("tr"):
            if "thead" in (tr.get("class") or []):
                continue
            if tr.find("th", {"data-stat": "player"}) is None:
                continue
            mp = tr.find("td", {"data-stat": "mp"})
            mp_text = mp.get_text(strip=True) if mp else ""
            if ":" in mp_text:
                mm, ss = mp_text.split(":")
                secs += int(mm) * 60 + int(ss)
                entered += 1
                avail += 1
                continue
            reason = tr.find("td", {"data-stat": "reason"})
            if reason is None:
                continue
            if reason.get_text(strip=True).lower() in NOT_AVAILABLE:
                continue
            avail += 1  # Did Not Play / Inactive
        out[code] = (avail, entered, secs)
    return out


# ---------------------------------------------------------------- scraping loop
def scrape(schedule):
    done = set()
    if os.path.exists(GAMES_CSV):
        with open(GAMES_CSV, newline="", encoding="utf-8") as f:
            done = {r["game_id"] for r in csv.DictReader(f)}
    new_file = not os.path.exists(GAMES_CSV)
    schedule = [g for g in schedule if involves_target(g[0], g[2], g[3])]
    total = len(schedule)
    print(f"{total} games involve the target teams\n")
    with open(GAMES_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["game_id", "team", "available", "entered", "seconds", "ot"])
            f.flush()
        for i, (gid, ot, _v, _h) in enumerate(schedule, start=1):
            if gid in done:
                continue
            html = fetch(f"https://www.basketball-reference.com/boxscores/{gid}.html")
            if html is None:
                print(f"[{i}/{total}] {gid}: FAILED -- run again later to retry")
                continue
            box = parse_box(html)
            if len(box) != 2:
                print(f"[{i}/{total}] {gid}: found {len(box)} team tables, skipping")
                continue
            for code, (a, e, s) in box.items():
                w.writerow([gid, code, a, e, s, 1 if ot else 0])
            f.flush()
            if i % 25 == 0 or i == total:
                print(f"[{i}/{total}] {gid} saved")
            time.sleep(DELAY)


# ---------------------------------------------------------------- summary
def summarize():
    agg = defaultdict(lambda: {"games": 0, "ot": 0, "avail": 0, "entered": 0, "secs": 0})
    with open(GAMES_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = agg[r["team"]]
            t["games"] += 1
            t["ot"] += int(r["ot"])
            t["avail"] += int(r["available"])
            t["entered"] += int(r["entered"])
            t["secs"] += int(r["seconds"])
    rows = []
    for code, t in agg.items():
        if code not in TARGETS:
            continue
        rows.append({
            "code": code, "team": TEAMS.get(code, code), "games": t["games"], "ot": t["ot"],
            "minutes": round(t["secs"] / 60, 1), "avail": t["avail"], "entered": t["entered"],
        })
    rows.sort(key=lambda r: r["team"])
    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "team", "games", "ot", "minutes", "avail", "entered"])
        w.writeheader()
        w.writerows(rows)

    print("\nChecks")
    for r in rows:
        if r["games"] != 82:
            print(f"  {r['team']}: {r['games']} games (expected 82)")
        if r["code"] in KNOWN and KNOWN[r["code"]] != (r["avail"], r["entered"]):
            print(f"  {r['team']}: Available/AGE = {r['avail']}/{r['entered']}, "
                  f"v5 PDF had {KNOWN[r['code']][0]}/{KNOWN[r['code']][1]}")
    if len(rows) != len(TARGETS):
        print(f"  Only {len(rows)}/{len(TARGETS)} teams so far -- run again to finish")
    return rows


def load_injuries():
    inj = {}
    if os.path.exists("injuries.csv"):
        with open("injuries.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("injuries", "").strip() != "":
                    inj[row["code"].strip().upper()] = int(row["injuries"])
    return inj


# ---------------------------------------------------------------- PDF (v5 layout)
def build_pdf(rows, inj):
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
    for r in rows:
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
        if r["code"] in inj:
            data.append(["Injuries recorded", str(inj[r["code"]])])
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
    lead = "" if inj else "Injury counts are excluded from this version. "
    story.append(Paragraph(
        f'Note: {lead}"Total players rostered" here reflects the game-day active/dressed roster '
        "(Available), not the full season roster or the official inactive list.", note))
    doc.build(story)
    print(f"PDF written to {PDF_OUT}")


def main():
    schedule = load_schedule()
    scrape(schedule)  # skips games already saved, so reruns make no requests once finished
    rows = summarize()
    build_pdf(rows, load_injuries())


if __name__ == "__main__":
    main()
