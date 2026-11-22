"""Game-specific NBA participation and reported absence reasons from ESPN."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache
from time import monotonic
from zoneinfo import ZoneInfo
import re
import requests
from lakers_test import classify_absence

BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'
ALIASES = {'WAS':'WSH','BRK':'BKN','CHO':'CHA','PHO':'PHX','GSW':'GS','NYK':'NY','NOP':'NO','SAS':'SA','UTA':'UTAH'}
EAST = {'ATL','BOS','BKN','CHA','CLE','DET','IND','MIA','NY','ORL','PHI','TOR','WSH'}
CENTRAL = {'CHI','DAL','HOU','MEM','MIL','MIN','NO','OKC','SA'}
WEST = {'GS','LAC','LAL','POR','SAC'}

def normalize(team):
    team = str(team).upper()
    team = ALIASES.get(team, team)
    if team not in EAST | CENTRAL | WEST | {'DEN','PHX','UTAH'}:
        raise ValueError('Choose a valid NBA team')
    return team

@lru_cache(maxsize=256)
def _fetch(path, bucket):
    response = requests.get(BASE + path, timeout=(5, 20))
    response.raise_for_status()
    data = response.json()
    if path.startswith('summary?'):
        # Retain only box-score data used by the app, not news or play-by-play.
        blocks = []
        for block in data.get('boxscore', {}).get('players', []):
            stats = []
            for section in block.get('statistics', []):
                rows = []
                for row in section.get('athletes', []):
                    athlete = row.get('athlete', {})
                    rows.append(dict(athlete={k:athlete[k] for k in ('id','displayName') if k in athlete},
                                     **{k:row[k] for k in ('stats','didNotPlay','reason') if k in row}))
                stats.append(dict(keys=section.get('keys'), labels=section.get('labels'), athletes=rows))
            blocks.append(dict(team=block.get('team', {}), statistics=stats))
        return dict(header=data.get('header', {}), gameInfo={'venue':data.get('gameInfo',{}).get('venue',{})}, boxscore={'players':blocks})
    return data

def fetch(path):
    # Bounded five-minute cache; no persistent public data files or credentials.
    return _fetch(path, int(monotonic() // 300))

def completed(event):
    competition = (event.get('competitions') or [{}])[0]
    status = event.get('status') or competition.get('status', {})
    return status.get('type', {}).get('completed') is True

def is_cup_final(event):
    notes = list(event.get('notes') or [])
    for competition in event.get('competitions', []):
        notes.extend(competition.get('notes') or [])
    text = ' '.join(str(note.get('headline','')) for note in notes if isinstance(note,dict))
    return bool(re.search(r'(nba cup|in-season tournament).*championship|championship.*(nba cup|in-season tournament)',text,re.I))


def schedule(team, season):
    try:
        data = fetch(f'teams/{team.lower()}/schedule?season={season}&seasontype=2')
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return []
        raise
    events = data.get('events')
    if not isinstance(events, list):
        raise ValueError('The source did not return a season schedule')
    # ESPN's top-level season can describe today, even for historical events.
    # Validate each event's year and exclude the Cup final, which is not a league game.
    return sorted([e for e in events if completed(e)
                   and e.get('season', {}).get('type', 2) == 2
                   and str(e.get('season', {}).get('year')) == str(season)
                   and not is_cup_final(e)], key=lambda e: (e.get('date',''),e['id']))

def local_date(event):
    competition = (event.get('competitions') or [event])[0]
    address = competition.get('venue', {}).get('address', {})
    state = address.get('state', '')
    home = next((c.get('team', {}).get('abbreviation') for c in competition.get('competitors',[]) if c.get('homeAway') == 'home'), '')
    if state == 'AZ' or home == 'PHX': zone = 'America/Phoenix'
    elif state in {'CA','WA','OR','NV'} or home in WEST: zone = 'America/Los_Angeles'
    elif state in {'CO','UT'} or home in {'DEN','UTAH'}: zone = 'America/Denver'
    elif state in {'IL','TX','TN','WI','MN','LA','OK'} or home in CENTRAL: zone = 'America/Chicago'
    elif home in EAST: zone = 'America/New_York'
    else: zone = 'UTC'
    return datetime.fromisoformat(event['date'].replace('Z','+00:00')).astimezone(ZoneInfo(zone)).date().isoformat(), zone

def parse_summary(data, team, event_id):
    competition = (data.get('header', {}).get('competitions') or [{}])[0]
    if competition.get('status', {}).get('type', {}).get('completed') is not True:
        raise ValueError('This game is not complete or has no final box score')
    block = next((b for b in data.get('boxscore', {}).get('players',[]) if b.get('team',{}).get('abbreviation') == team), None)
    if block is None:
        raise ValueError(f'No player box score returned for {team}')
    players, seen = [], set()
    for stats in block.get('statistics', []):
        keys = stats.get('keys') or stats.get('labels') or []
        minute_index = next((i for i,k in enumerate(keys) if k in ('minutes','MIN')), None)
        for row in stats.get('athletes', []):
            athlete = row.get('athlete', {})
            player_id = athlete.get('id')
            if not player_id or player_id in seen:
                continue
            seen.add(player_id)
            values = row.get('stats') or []
            minutes = values[minute_index] if minute_index is not None and len(values) > minute_index else None
            valid_minutes = bool(re.fullmatch(r'\d+(?::\d{2})?(?:\.\d+)?', str(minutes)))
            did_not_play = row.get('didNotPlay')
            if did_not_play is True and not valid_minutes:
                played = False
            elif did_not_play is not True and valid_minutes:
                played = True
            else:
                played = None  # Contradictory/missing source participation data.

            # ESPN also attaches default reason strings to played players: ignore them.
            reason = row.get('reason') if played is not True else None
            if not isinstance(reason, str) or not reason.strip(): reason = None
            players.append(dict(player=athlete.get('displayName','Unknown player'), player_id=player_id,
                                played=played, minutes=minutes if played is True else None,
                                reported_minutes=minutes, source_did_not_play=did_not_play,
                                participation_status='played' if played is True else ('absent' if played is False else 'unknown'),
                                reported_absence_reason=reason,
                                absence_category=classify_absence(reason) if played is False else None))
    if not players or not any(p['played'] is True for p in players):
        raise ValueError('No completed player participation data found')
    counts = {c:sum(p['absence_category']==c for p in players) for c in ('injury','illness','other','unknown')}
    competitors = competition.get('competitors', [])
    own = next((c for c in competitors if c.get('team',{}).get('abbreviation')==team), {})
    opponent = next((c for c in competitors if c.get('team',{}).get('abbreviation')!=team), {})
    periods = [len(c.get('linescores', [])) for c in competitors]
    if not periods or max(periods) < 4:
        raise ValueError('Completed game is missing period totals')
    overtime = max(periods) - 4
    event = dict(competition, date=competition.get('date') or data['header'].get('date'), venue=data.get('gameInfo',{}).get('venue',{}))
    date, zone = local_date(event)
    return dict(game_id=str(event_id), team_code=team, team_name=block.get('team',{}).get('displayName') or own.get('team',{}).get('displayName') or team,
                season_end_year=data.get('header',{}).get('season',{}).get('year'),
                opponent_name=opponent.get('team',{}).get('displayName') or opponent.get('team',{}).get('abbreviation'), date=date, date_timezone=zone, opp=opponent.get('team',{}).get('abbreviation','?'),
                wl='W' if own.get('winner') is True else ('L' if own.get('winner') is False else '?'),
                minutes_played=240+25*overtime, minutes_basis='Five players × completed period lengths',
                overtime_periods=overtime, players_entered=sum(p['played'] is True for p in players),
                participation_unknown=sum(p['played'] is None for p in players),
                players_dnp=sum(counts.values()), injured_out=counts['injury'], absence_counts=counts, players=players,
                source_url=f'https://www.espn.com/nba/boxscore/_/gameId/{event_id}')

def game(event_id, team):
    from nba_official_reports import enrich_game
    data=fetch(f'summary?event={event_id}')
    return enrich_game(parse_summary(data,team,event_id),data,team)

def participation_warnings(games):
    count = sum(g.get('participation_unknown',0) for g in games)
    warnings=[]
    if count:warnings.append(f'{count} player-game record(s) have uncertain participation. They are shown separately and excluded from entered-player and absence counts.')
    unavailable=sum(g.get('official_report',{}).get('status')!='available' for g in games)
    if unavailable:warnings.append(f'Official injury reports are unavailable for {unavailable} of {len(games)} collected games. Missing report coverage is not zero injuries.')
    return warnings


def collect_dashboard(mode, team, season, max_games=10, game_id=''):
    team = normalize(team)
    if not re.fullmatch(r'\d{4}',str(season)) or not 1947 <= int(season) <= 9999:
        raise ValueError('Choose a valid season end year')
    if mode == 'game':
        if not re.fullmatch(r'\d{6,12}',str(game_id)):
            raise ValueError('Enter the numeric ESPN game ID from a box-score URL, for example 401704628')
        metrics = game(game_id,team)
        return dict(mode=mode,game_id=game_id,metrics=metrics,warnings=participation_warnings([metrics]),output='')
    if mode not in ('team','roster'): raise ValueError('Unknown mode')
    if isinstance(max_games, bool) or not re.fullmatch(r'\d+', str(max_games)):
        raise ValueError('Choose a whole number of games between 1 and 100')
    limit=int(max_games)
    if not 1<=limit<=100: raise ValueError('Choose between 1 and 100 games')
    events = schedule(team,season)[:limit]
    if not events: raise ValueError('No completed regular-season games available for this season')
    def load(event):
        try: return game(event['id'],team),None
        except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
            return None,f"Game {event['id']}: unavailable ({type(exc).__name__})"
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(load,events))
    games=[g for g,w in results if g is not None]
    warnings=[w for g,w in results if w] + participation_warnings(games)
    if not games: raise ValueError('No box scores could be collected. Source data is unavailable, not zero absences.')
    if mode=='roster':
        players={p['player_id']:p['player'] for g in games for p in g['players']}
        return dict(mode=mode,roster_count=len(players),output='\n'.join(sorted(players.values())),
                    warnings=warnings,collected_games=len(games),requested_games=len(events))
    return dict(mode=mode,games=games,warnings=warnings,requested_games=len(events),output='')
