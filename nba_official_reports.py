"""Official NBA injury-report snapshots, joined without inventing final availability."""
from datetime import datetime, timedelta
from functools import lru_cache
from io import BytesIO
import re
import unicodedata
from time import monotonic, sleep
from zoneinfo import ZoneInfo
import requests
from pypdf import PdfReader
from lakers_test import classify_absence

ET = ZoneInfo('America/New_York')
TEAM_CODES = {'Atlanta Hawks':'ATL','Boston Celtics':'BOS','Brooklyn Nets':'BKN','Charlotte Hornets':'CHA','Chicago Bulls':'CHI','Cleveland Cavaliers':'CLE','Dallas Mavericks':'DAL','Denver Nuggets':'DEN','Detroit Pistons':'DET','Golden State Warriors':'GS','Houston Rockets':'HOU','Indiana Pacers':'IND','LA Clippers':'LAC','Los Angeles Clippers':'LAC','Los Angeles Lakers':'LAL','Memphis Grizzlies':'MEM','Miami Heat':'MIA','Milwaukee Bucks':'MIL','Minnesota Timberwolves':'MIN','New Orleans Pelicans':'NO','New York Knicks':'NY','Oklahoma City Thunder':'OKC','Orlando Magic':'ORL','Philadelphia 76ers':'PHI','Phoenix Suns':'PHX','Portland Trail Blazers':'POR','Sacramento Kings':'SAC','San Antonio Spurs':'SA','Toronto Raptors':'TOR','Utah Jazz':'UTAH','Washington Wizards':'WSH'}
REASON_PREFIX = re.compile(r'^(Injury\s*/\s*Illness|Concussion\s+Protocol|G\s+League|Return\s+to\s+Competition|Not\s+With\s+Team|Personal|Rest|Suspension|League\s+Suspension|Team\s+Suspension|Coach[’\']?s?\s+Decision|Other)', re.I)
STATUSES = {'Out','Questionable','Doubtful','Probable','Available'}

def clean(text):
    return re.sub(r'\s+', ' ', text).strip().replace('Two- Way','Two-Way')

def clean_name(text):
    return re.sub(r'(?<=\w)-\s+(?=\w)', '-', clean(text))

def name_key(name):
    text = unicodedata.normalize('NFKD', name or '')
    return re.sub(r'[^a-z0-9]', '', text.encode('ascii','ignore').decode().lower())

def report_category(reason):
    # Injury/Illness is a report section heading, not evidence of both conditions.
    detail = re.sub(r'^Injury\s*/\s*Illness\s*[-–:]?\s*','',reason,flags=re.I)
    return classify_absence(detail)

def parse_report(content, source_url):
    reader = PdfReader(BytesIO(content))
    plain = reader.pages[0].extract_text()
    match = re.search(r'Injury\s+Report:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})\s*([AP]M)',plain,re.I)
    if not match: raise ValueError('Unrecognized NBA report timestamp')
    date_format = '%m/%d/%y' if len(match[1].split('/')[-1])==2 else '%m/%d/%Y'
    timestamp = datetime.strptime(f'{match[1]} {match[2]} {match[3].upper()}',date_format+' %I:%M %p').replace(tzinfo=ET)
    anchors, reason_lines = [], []
    columns = None
    legacy_category = False
    for page_no,page in enumerate(reader.pages):
        if getattr(page, 'rotation', 0):page.transfer_rotation_to_content()
        words=[]
        def visit(text,cm,tm,font,size):
            if text.strip():
                x=tm[4]*cm[0]+tm[5]*cm[2]+cm[4]
                y=float(page.mediabox.height)-(tm[4]*cm[1]+tm[5]*cm[3]+cm[5])
                words.append(dict(x=x,y=y,text=clean(text)))
        page.extract_text(visitor_text=visit)
        headings={}
        for word in words:
            for heading in ('Team','Player','Current','Reason','Matchup','Category','Previous'):
                if word['text'].split()[0]==heading and word['y']<190:headings[heading]=word
        if all(k in headings for k in ('Team','Player','Current','Reason','Matchup')):
            legacy_category = 'Category' in headings
            columns={key:value['x']-2 for key,value in headings.items()}
            top=max(value['y'] for value in headings.values())+3
        elif columns:
            top=75
        else:raise ValueError('Unrecognized NBA report table columns')
        lines={}
        for word in words:
            if not top<word['y']<float(page.mediabox.height)-35:continue
            key=round(word['y'], 1)
            lines.setdefault(key,[]).append(word)
        page_anchors=[]
        for y,words_in_line in sorted(lines.items()):
            fields={'date':[],'matchup':[],'team':[],'name':[],'status':[],'reason':[],'category':[]}
            for w in sorted(words_in_line,key=lambda w:w['x']):
                x=w['x']
                boundaries={'Reason':'reason','Current':'status','Player':'name','Team':'team','Matchup':'matchup','Category':'category','Previous':'previous'}
                column=next((k for k in sorted(columns,key=columns.get,reverse=True) if x>=columns[k]),None)
                if column=='Previous':continue
                if column:key=boundaries[column]
                elif re.fullmatch(r'\d{2}/\d{2}/\d{4}',w['text']):key='date'
                else:continue
                fields[key].append(w['text'])
            fields={k:clean(' '.join(v)) for k,v in fields.items()}
            position=page_no*10000+y
            if fields['status'] in STATUSES or fields['reason']=='NOT YET SUBMITTED':
                page_anchors.append(dict(legacy_category=legacy_category,position=position,page=page_no,y=y,height=float(page.mediabox.height),**fields))
            if fields['reason'] and fields['reason']!='NOT YET SUBMITTED':
                reason_lines.append(dict(position=position,page=page_no,y=y,text=fields['reason']))
        anchors.extend(page_anchors)
    actual=[a for a in anchors if a['status'] in STATUSES]
    # Group physically contiguous reason baselines first. Reason cells are
    # vertically centred against the player/status row, including wrapped cells
    # that begin above that row. A repeated phrase such as Concussion Protocol
    # is therefore never mistaken for a new player's reason.
    blocks=[]
    for line in reason_lines:
        if blocks and blocks[-1]['page']==line['page'] and line['y']-blocks[-1]['bottom']<=16:
            blocks[-1]['lines'].append(line['text']);blocks[-1]['bottom']=line['y']
        else:
            blocks.append(dict(page=line['page'],top=line['y'],bottom=line['y'],lines=[line['text']]))
    assigned={id(a):[] for a in actual}
    for block in blocks:
        candidates=[a for a in actual if a['page']==block['page']]
        center=(block['top']+block['bottom'])/2
        distances=sorted(((abs(a['y']-center),i,a) for i,a in enumerate(candidates)),key=lambda item:item[:2])
        target=None
        if distances and distances[0][0]<=10 and (len(distances)==1 or distances[1][0]-distances[0][0]>2):
            target=distances[0][2]
        else:
            # The PDF can continue a reason at the top of the next page while
            # its player/status remains at the bottom of the previous page.
            previous=[a for a in actual if a['page']==block['page']-1]
            text=clean(' '.join(block['lines']))
            if (previous and block['top']<=105 and
                previous[-1]['y']>=previous[-1]['height']-110 and
                not REASON_PREFIX.match(text) and text!='-' and
                assigned[id(previous[-1])]):
                target=previous[-1]
        if target is None:
            raise ValueError('NBA report rows do not reconcile: reason has no unique positional row')
        if assigned[id(target)] and target['page']==block['page']:
            raise ValueError('NBA report rows do not reconcile: multiple reason blocks for one row')
        assigned[id(target)].extend(block['lines'])
    for a in actual:
        a['resolved_reason']=clean(' '.join(assigned[id(a)]))
        if not a['resolved_reason'] or not (a['legacy_category'] or REASON_PREFIX.match(a['resolved_reason']) or a['resolved_reason']=='-' or a['resolved_reason']=='Health and Safety Protocols'):
            raise ValueError('NBA report rows do not reconcile: missing or unrecognized reason')
    records=[];not_submitted=[];matchups=set();current_date=current_matchup=current_team=''
    for a in anchors:
        if a['date']:current_date=datetime.strptime(a['date'],'%m/%d/%Y').date().isoformat()
        if a['matchup']:current_matchup=a['matchup']
        if a['team']:current_team=a['team']
        if not current_date or not current_matchup or current_team not in TEAM_CODES:
            raise ValueError('NBA report row lacks an unambiguous date, matchup or team')
        matchups.add((current_date,current_matchup))
        if a['reason']=='NOT YET SUBMITTED':
            not_submitted.append((current_date,current_matchup,TEAM_CODES[current_team]));continue
        reason=a['resolved_reason']
        if a['legacy_category'] and a['category']:reason=a['category']+' - '+reason
        if ',' not in a['name']:raise ValueError('NBA report player name is incomplete')
        last,first=a['name'].split(',',1)
        full_name=clean_name(first+' '+last)
        records.append(dict(player_full_name=full_name,source_player_name=clean_name(a['name']),source_player_name_raw=a['name'],team= current_team,
                            team_code=TEAM_CODES[current_team],game_date=current_date,matchup=current_matchup,
                            source_category=a['category'] or None,source_reason=a['resolved_reason'],reported_status=a['status'],reported_reason=reason,category=report_category(reason),
                            report_at=timestamp.isoformat(),source_url=source_url))
    return dict(report_at=timestamp.isoformat(),source_url=source_url,records=records,
                not_submitted=not_submitted,matchups=sorted(matchups))


def snapshot_candidates(tipoff):
    """Bounded documented filename formats; actual PDF timestamp is validated below."""
    local=tipoff.astimezone(ET)
    cutoff=local-timedelta(minutes=1)
    modern=cutoff.replace(minute=cutoff.minute//15*15,second=0,microsecond=0)
    legacy=(local-timedelta(minutes=31)).replace(minute=0,second=0,microsecond=0)
    first=[(modern,True),(legacy,False)] if local.year>=2026 else [(legacy,False),(modern,True)]
    choices=first
    for hour in (20,17,13,7):
        point=local.replace(hour=hour,minute=0,second=0,microsecond=0)
        choices.extend([(point,False),(point,True)])
    previous=(local-timedelta(days=1)).replace(hour=20,minute=0,second=0,microsecond=0)
    choices.extend([(previous,False),(previous,True)])
    seen=set()
    for choice,new_format in choices:
        if choice>=local:continue
        suffix=choice.strftime('%I_%M%p' if new_format else '%I%p')
        url=f'https://ak-static.cms.nba.com/referee/injury/Injury-Report_{choice:%Y-%m-%d}_{suffix}.pdf'
        if url not in seen:seen.add(url);yield url

@lru_cache(maxsize=512)
def _fetch_report(url, bucket):
    for attempt in range(3):
        try:
            response=requests.get(url,timeout=(3,8))
            if response.status_code in (403,404):return None
            response.raise_for_status()
            if not response.content.startswith(b'%PDF'):raise ValueError('Source returned non-PDF content')
            try:return parse_report(response.content,url)
            except Exception as exc:raise ValueError('Official PDF layout or content could not be verified') from exc
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            code=exc.response.status_code if exc.response is not None else None
            if attempt==2 or (code is not None and code!=429 and code<500):raise
            sleep(.25 * 2**attempt)
    # Exceptions are deliberately not cached; a refresh can recover immediately.

def fetch_report(url):
    return _fetch_report(url,int(monotonic()//300))


def official_for_game(tipoff_iso, team, matchup):
    tipoff=datetime.fromisoformat(tipoff_iso.replace('Z','+00:00'))
    day=tipoff.astimezone(ET).date().isoformat()
    deadline=monotonic()+25
    failures=set()
    for url in snapshot_candidates(tipoff):
        if monotonic()>deadline:
            failures.add('search_incomplete');break
        try:report=fetch_report(url)
        except requests.RequestException:
            failures.add('fetch_failed');continue
        except ValueError:
            failures.add('parse_failed');continue
        if report is None:continue
        asof=datetime.fromisoformat(report['report_at'])
        if not tipoff-timedelta(hours=36)<asof<tipoff:continue
        if (day,matchup) not in [tuple(m) for m in report['matchups']]:continue
        if (day,matchup,team) in [tuple(m) for m in report['not_submitted']]:continue
        records=[dict(r) for r in report['records'] if r['game_date']==day and r['matchup']==matchup and r['team_code']==team]
        return dict(status='available',report_at=report['report_at'],source_url=url,records=records,
                    note='Selected available pregame snapshot; later updates or unreported injuries may exist. Not a new-injury count.')
    return dict(status='unavailable',records=[],report_at=None,source_url=None,
                retrieval_status=('fetch_failed' if 'fetch_failed' in failures else 'parse_failed' if 'parse_failed' in failures else 'search_incomplete' if failures else 'no_matching_snapshot'),
                note=('Report retrieval failed; retry this query. ' if 'fetch_failed' in failures else 'Report layout could not be verified. ' if 'parse_failed' in failures else 'The bounded snapshot search found no matching submitted report; this does not prove none was published. ')+'Injury counts are unavailable, not zero.')


def enrich_game(metrics, data, team):
    competition=data['header']['competitions'][0]
    competitors=competition.get('competitors',[])
    def report_code(code):return {'GS':'GSW','NY':'NYK','NO':'NOP','SA':'SAS','UTAH':'UTA','WSH':'WAS'}.get(code,code)
    away=next((c['team']['abbreviation'] for c in competitors if c.get('homeAway')=='away'),None)
    home=next((c['team']['abbreviation'] for c in competitors if c.get('homeAway')=='home'),None)
    if not away or not home:raise ValueError('Game lacks an official-report matchup')
    report=official_for_game(competition['date'],team,report_code(away)+'@'+report_code(home))
    for record in report['records']:
        matches=[p for p in metrics['players'] if name_key(p['player'])==name_key(record['player_full_name'])]
        player=matches[0] if len(matches)==1 else None
        record['player_id']=player['player_id'] if player else None
        record['actual_participation']=player['participation_status'] if player else 'not_listed_in_box_score'
        record['reported_minutes']=player.get('reported_minutes') if player else None
        record['join_method']='exact_normalized_name' if player else 'unmatched'
        record['record_type']='official_pregame_designation'
    metrics['official_report']=report
    metrics['official_report_counts']={c:sum(r['category']==c for r in report['records']) for c in ('injury','illness','other','unknown')} if report['status']=='available' else None
    return metrics
