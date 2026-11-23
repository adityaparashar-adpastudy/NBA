import argparse,time,re,json,requests,pandas as pd
from bs4 import BeautifulSoup,Comment
from io import StringIO
HEADERS={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
DELAY=3
def get_soup(url):
    time.sleep(DELAY)
    r=requests.get(url,headers=HEADERS,timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text,"lxml")
def flatten_columns(df):
    if isinstance(df.columns,pd.MultiIndex):
        new_cols=[]
        for col in df.columns:
            parts=[str(c) for c in col if not str(c).startswith("Unnamed")]
            new_cols.append(parts[-1] if parts else str(col[-1]))
        df.columns=new_cols
    return df
def find_table(soup,table_id):
    t=soup.find("table",id=table_id)
    if t: return t
    for comment in soup.find_all(string=lambda t:isinstance(t,Comment)):
        if table_id in comment:
            inner=BeautifulSoup(comment,"lxml")
            t=inner.find("table",id=table_id)
            if t: return t
    return None
def parse_minutes(mp_str):
    try:
        p=str(mp_str).split(":")
        return int(p[0])+int(p[1])/60
    except: return 0.0
def get_roster(team,season):
    url=f"https://www.basketball-reference.com/teams/{team}/{season}.html"
    soup=get_soup(url)
    table=find_table(soup,"roster")
    if not table: return pd.DataFrame()
    df=pd.read_html(StringIO(str(table)))[0]
    df=flatten_columns(df)
    pc=next((c for c in df.columns if "Player" in c),None)
    if pc: df=df[df[pc].notna()&(df[pc]!="Player")]
    return df
def classify_absence(reason):
    """Classify only explicit source wording; generic DNP is unknown."""
    text = re.sub(r"\s+", " ", (reason or "").lower().replace("’", "\'")).strip()
    # The report section heading is not evidence of two separate conditions.
    text = re.sub(r"^injury\s*/\s*illness\s*[-–:]\s*(?=\S)", "", text)
    injury = bool(re.search(r"\b(injury|injured|sprain(?:ed)?|strain(?:ed)?|fractur(?:e|ed)|broken|bruise(?:d)?|soreness|sore|contusion|concussion|surgery|surgical|torn|tear|tendinitis|tendinopathy|ankle|knee|hamstring|achilles|groin|back|wrist|shoulder|foot|toe|thumb|hip|quad|calf|leg|hand|finger|elbow|heel|acl|mcl|pcl|lcl|oblique|adductor|abductor|neck|rib(?:s)?|sternum|face|rotator cuff|plantar fasci(?:a|itis)|tendonitis|nerves?|sciatic\w*|patello\w*|patellar|tendons?|plantar|retrocalcaneal|corneal|eye|metatarsal\w*|tibia\w*|facet|core|patella\w*|tendonopathy|laceration|disc|disk|lumbar|spinal|spine|post[ -]traumatic)\b", text))
    illness = bool(re.search(r"\b(illness|ill|respiratory|flu|influenza|covid(?:-19)?|gastroenteritis|migraine|virus|viral|strep(?: throat)?)\b", text))
    other = bool(re.search(r"coach[’']?s? decision|\b(personal|rest|suspended|suspension|g league|g-league|assignment|not with team|trade pending)\b", text))
    categories = [name for name, flag in [('injury', injury), ('illness', illness), ('other', other)] if flag]
    return categories[0] if len(categories) == 1 else 'unknown'


def parse_boxscore(soup, game_id, team):
    table = find_table(soup, f"box-{team}-game-basic")
    if table is None:
        raise ValueError(f"Box score unavailable for {team}: {game_id}")
    players = []
    for row in table.select('tbody tr'):
        name_cell = row.select_one('[data-stat="player"]')
        if name_cell is None or not name_cell.get('data-append-csv'):
            continue  # headings and totals are not players
        mp_cell = row.select_one('[data-stat="mp"]')
        dnp_cell = row.select_one('[data-stat="reason"], [data-stat="dnp"]')
        mp = mp_cell.get_text(' ', strip=True) if mp_cell else ''
        played = bool(re.fullmatch(r"\d+:\d{2}", mp))
        # Retain the exact extracted source text; do not manufacture a reason.
        reason = dnp_cell.get_text(' ', strip=True) if dnp_cell else (mp if not played else '')
        if not played and not reason:
            reason = None
        category = None if played else classify_absence(reason)
        players.append(dict(player=name_cell.get_text(' ', strip=True),
                            player_id=name_cell['data-append-csv'], played=played,
                            minutes=mp if played else None, reported_absence_reason=reason,
                            absence_category=category))
    if not players or not any(player['played'] for player in players):
        raise ValueError('No completed player participation data found in box score')
    counts = {category: sum(player['absence_category'] == category for player in players)
              for category in ('injury', 'illness', 'other', 'unknown')}
    total_min = sum(parse_minutes(player['minutes']) for player in players if player['played'])
    return dict(minutes_played=round(total_min, 1),
                overtime_periods=max(0, round((total_min - 240) / 25)),
                players_entered=sum(player['played'] for player in players),
                players_dnp=sum(counts.values()), injured_out=counts['injury'],
                absence_counts=counts, players=players,
                source_url=f'https://www.basketball-reference.com/boxscores/{game_id}.html')


def get_game_metrics(game_id,team):
    url=f"https://www.basketball-reference.com/boxscores/{game_id}.html"
    return parse_boxscore(get_soup(url), game_id, team)


def collect_dashboard(mode, team, season, max_games=10, game_id=''):
    if not re.fullmatch(r'[A-Z]{3}', team) or not re.fullmatch(r'\d{4}', str(season)):
        raise ValueError('Choose a valid team and season')
    if mode == 'roster':
        roster = get_roster(team, season)
        if roster.empty:
            raise ValueError('Season roster unavailable from source')
        return dict(mode=mode, roster_count=len(roster), output=roster.to_string(index=False))
    if mode == 'game':
        if not re.fullmatch(r'\d{9}[A-Z]{3}', game_id):
            raise ValueError('Use a box-score ID such as 202410220BOS')
        return dict(mode=mode, game_id=game_id, metrics=get_game_metrics(game_id, team), output='')
    if mode != 'team':
        raise ValueError('Unknown mode')
    limit = int(max_games)
    if not 1 <= limit <= 100:
        raise ValueError('Choose between 1 and 100 games')
    log = get_game_log(team, season)
    if log.empty:
        raise ValueError('No completed games available from source for this season')
    games, warnings = [], []
    for _, row in log.head(limit).iterrows():
        gid = row.get('game_id')
        try:
            if not gid:
                raise ValueError('Missing game ID')
            metrics = get_game_metrics(gid, team)
            games.append(dict(metrics, date=str(row.get('Date', '')), opp=str(row.get('Opp', '?')),
                              wl=str(row.get('W/L', row.get('Rslt', '?'))), game_id=gid))
        except (requests.RequestException, ValueError) as exc:
            warnings.append(f"{gid}: {exc}")
    if not games:
        raise ValueError('No box scores could be collected. Try again later; missing data is not zero absences.')
    return dict(mode=mode, games=games, warnings=warnings, requested_games=min(limit, len(log)), output='')

def get_game_log(team,season):
    url=f"https://www.basketball-reference.com/teams/{team}/{season}/gamelog/"
    soup=get_soup(url)
    table=find_table(soup,"team_game_log_reg") or find_table(soup,"tgl_basic")
    if not table:
        print("ERROR: game log table not found.")
        return pd.DataFrame()
    df=pd.read_html(StringIO(str(table)))[0]
    df=flatten_columns(df)
    rk=next((c for c in df.columns if c in("Rk","G","Gtm")),None)
    if rk: df=df[pd.to_numeric(df[rk],errors="coerce").notna()].copy()
    if "Date" not in df.columns:
        dc=next((c for c in df.columns if "Date" in str(c)),None)
        if dc: df=df.rename(columns={dc:"Date"})
    if "Date" in df.columns: df=df[df["Date"].notna()&(df["Date"]!="Date")].copy()
    opp_col=next((c for c in df.columns if c=="Opp"),None)
    wl_col=next((c for c in df.columns if c in("W/L","Rslt")),None)
    loc_col=None
    for c in df.columns:
        if "Unnamed" in str(c):
            vals=df[c].astype(str).str.strip().unique()
            if set(vals).issubset({"@","","nan"}):
                loc_col=c
                break
    game_ids=[]
    for _,row in df.iterrows():
        ds=str(row.get("Date","")).replace("-","")
        if len(ds)!=8:
            game_ids.append(None)
            continue
        opp=str(row.get(opp_col,"UNK")).strip() if opp_col else "UNK"
        is_away=loc_col and str(row.get(loc_col,"")).strip()=="@"
        home=opp if is_away else team
        game_ids.append(f"{ds}0{home}")
    df["game_id"]=game_ids
    keep=[c for c in ["Date",opp_col,wl_col,"game_id"] if c and c in df.columns]
    return df[keep].copy()
def cmd_game(game_id,team):
    team=team.upper()
    print(f"Fetching metrics for game {game_id} ({team})...")
    m=get_game_metrics(game_id,team)
    if not m:
        print("ERROR: Could not find boxscore.")
        return
    print("  Absence categories:", m['absence_counts'])
    for player in m['players']:
        if not player['played']:
            print(f"  {player['player']} | {player['absence_category']} | {player['reported_absence_reason'] or 'Not reported'}")
    ot=f"  (+{m['overtime_periods']} OT)" if m["overtime_periods"] else ""
    print(f"-- {team} | Game: {game_id} --")
    print(f"  1. Injury-related absences               : {m['injured_out']} player(s)")
    print(f"  2. Total minutes played         : {m['minutes_played']} min{ot}")
    print(f"  3. Players who entered the game : {m['players_entered']}")
    print(f"  4. Players who did NOT play     : {m['players_dnp']}")
def cmd_team(team,season,max_games):
    team=team.upper()
    print(f"Fetching {team} roster ({season})...")
    roster_df=get_roster(team,season)
    roster_size=len(roster_df)
    print(f"Roster size: {roster_size} players (metric 4 baseline)")
    print(f"Fetching {team} game log ({season})...")
    game_log=get_game_log(team,season)
    if game_log.empty: return
    rows=[]
    for i,(_,row) in enumerate(game_log.iterrows()):
        if i>=max_games: break
        gid=row.get("game_id")
        opp=row.get("Opp","?")
        wl=row.get("W/L",row.get("Rslt","?"))
        date=row.get("Date","?")
        if not gid: continue
        print(f"  [{i+1}/{max_games}] {date} vs {opp} ({wl})  -> {gid}")
        m=get_game_metrics(gid,team)
        if not m:
            print("    Could not fetch boxscore, skipping.")
            continue
        rows.append({"Date":date,"Opp":opp,"W/L":wl,"1. Injury-related absences":m["injured_out"],"2. Mins Played":m["minutes_played"],"OT Periods":m["overtime_periods"],"3. Entered Game":m["players_entered"],"Players DNP":m["players_dnp"],"4. Roster Size":roster_size, **{f"Absences {k}":v for k,v in m["absence_counts"].items()}, "Source URL":m["source_url"], "Player absence records":json.dumps([player for player in m["players"] if not player["played"]],ensure_ascii=False)})
    if not rows:
        print("No data collected.")
        return
    summary=pd.DataFrame(rows)
    print("="*80)
    print(f"  {team} -- {season} Season  ({len(summary)} games)")
    print("="*80)
    print(summary.to_string(index=False))
    out=f"{team}_game_metrics_{season}.csv"
    summary.to_csv(out,index=False)
    print(f"Saved to: {out}")
def cmd_roster(team,season):
    team=team.upper()
    print(f"Fetching {team} roster ({season})...")
    df=get_roster(team,season)
    if df.empty:
        print("No roster data found.")
        return
    print(df.to_string(index=False))
    print(f"Total: {len(df)} players")
def main():
    parser=argparse.ArgumentParser(description="NBA 4-Metric Scraper")
    parser.add_argument("--game_id")
    parser.add_argument("--team")
    parser.add_argument("--roster")
    parser.add_argument("--season",default="2025")
    parser.add_argument("--max_games",type=int,default=10)
    args=parser.parse_args()
    if args.game_id and args.team: cmd_game(args.game_id,args.team)
    elif args.team: cmd_team(args.team,args.season,args.max_games)
    elif args.roster: cmd_roster(args.roster,args.season)
    else: parser.print_help()
if __name__=="__main__":
    main()
