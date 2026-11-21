import argparse,time,requests,pandas as pd
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
def get_game_metrics(game_id,team):
    url=f"https://www.basketball-reference.com/boxscores/{game_id}.html"
    soup=get_soup(url)
    table=find_table(soup,f"box-{team}-game-basic")
    if not table: return None
    df=pd.read_html(StringIO(str(table)))[0]
    df=flatten_columns(df)
    if "MP" in df.columns: df=df[df["MP"]!="MP"].copy()
    dnp_flags=["Did Not Play","Did Not Dress","Not With Team"]
    played=df[df["MP"].notna()&~df["MP"].isin(dnp_flags)].copy()
    dnp=df[df["MP"].isin(dnp_flags)].copy()
    injured=dnp[dnp["MP"]=="Did Not Play"]
    total_min=played["MP"].apply(parse_minutes).sum()
    ot=max(0,round((total_min-240)/25)) if total_min>241 else 0
    return {"minutes_played":round(total_min,1),"overtime_periods":ot,"players_entered":len(played),"players_dnp":len(dnp),"injured_out":len(injured)}
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
    ot=f"  (+{m['overtime_periods']} OT)" if m["overtime_periods"] else ""
    print(f"-- {team} | Game: {game_id} --")
    print(f"  1. Injuries (DNP)               : {m['injured_out']} player(s)")
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
        rows.append({"Date":date,"Opp":opp,"W/L":wl,"1. Injuries DNP":m["injured_out"],"2. Mins Played":m["minutes_played"],"OT Periods":m["overtime_periods"],"3. Entered Game":m["players_entered"],"Players DNP":m["players_dnp"],"4. Roster Size":roster_size})
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
