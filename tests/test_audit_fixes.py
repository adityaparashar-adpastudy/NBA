import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import requests
from nba_dashboard import app
from lakers_test import classify_absence
from nba_espn_collector import schedule,collect_dashboard,parse_summary,participation_warnings
DATA=json.loads((Path(__file__).parent/'fixtures/espn_lal_401704628.json').read_text())
def event(year=2025,note=None,event_id='1'):
    return dict(id=event_id,date=f'{year-1}-12-18T02:00Z',season={'year':year},status={'type':{'completed':True}},competitions=[dict(notes=[{'headline':note}] if note else [])])
class AuditFixTests(unittest.TestCase):
    def test_explicit_injury_wording(self):
        for reason in ['RIGHT ACL','BROKEN HAND','LEFT HAND','FRACTURED RIBS','LOWER LEG','LEFT ABDUCTOR','LEFT OBLIQUE','SPRAINED RIGHT FINGER','RIGHT ADDUCTOR','NECK SPASMS','ROTATOR CUFF','RIGHT PATELLAR TENDONITIS','STERNUM','FACE','BONE BRUISE','PLANTAR FASCIITIS']:
            with self.subTest(reason=reason):self.assertEqual(classify_absence(reason),'injury')
        self.assertEqual(classify_absence('TRADE PENDING'),'other')
    def test_ambiguous_stays_unknown(self):
        for reason in ['INJURY/ILLNESS','RETURN TO COMPETITION RECONDITIONING','DID NOT DRESS','']:
            self.assertEqual(classify_absence(reason),'unknown')
    def test_cup_finals_and_wrong_year_excluded(self):
        data={'season':{'year':2027},'events':[event(),event(note='NBA Cup Championship',event_id='2'),event(note='NBA In-Season Tournament Championship',event_id='3'),event(year=2024,event_id='4')]}
        with patch('nba_espn_collector.fetch',return_value=data):self.assertEqual([e['id'] for e in schedule('LAL','2025')],['1'])
    def test_cup_group_and_knockout_games_stay(self):
        data={'events':[event(note='NBA Cup - Quarterfinal',event_id='1'),event(note='NBA Cup - Group Play',event_id='2')]}
        with patch('nba_espn_collector.fetch',return_value=data):self.assertEqual(len(schedule('LAL','2025')),2)
    def test_future_year_no_wrong_season_fallback(self):
        with patch('nba_espn_collector.fetch',return_value={'events':[event(year=2025)]}):
            for year in ['2028','2029','2040']:
                with self.assertRaisesRegex(ValueError,'No completed regular-season games'):collect_dashboard('team','LAL',year,5)
    def test_future_year_404_is_no_data(self):
        response=requests.Response();response.status_code=404
        with patch('nba_espn_collector.fetch',side_effect=requests.HTTPError(response=response)):
            self.assertEqual(schedule('LAL','2029'),[])
    def test_source_outage_not_empty_season(self):
        response=requests.Response();response.status_code=503
        with patch('nba_espn_collector.fetch',side_effect=requests.HTTPError(response=response)):
            with self.assertRaises(requests.HTTPError):schedule('LAL','2029')
    def test_contradictory_dnp_flag(self):
        d=copy.deepcopy(DATA);row=d['boxscore']['players'][1]['statistics'][0]['athletes'][0];row['didNotPlay']=True
        m=parse_summary(d,'LAL','401704628');p=m['players'][0]
        self.assertIsNone(p['played']);self.assertIsNone(p['absence_category']);self.assertEqual(m['participation_unknown'],1)
        self.assertEqual(m['players_dnp'],3);self.assertIn('excluded',participation_warnings([m])[0])
    def test_missing_minutes_source_text_retained(self):
        d=copy.deepcopy(DATA);row=d['boxscore']['players'][1]['statistics'][0]['athletes'][0];row['stats'][0]='--';row['reason']='LEFT HAND'
        m=parse_summary(d,'LAL','401704628');p=m['players'][0]
        self.assertEqual(p['reported_minutes'],'--');self.assertEqual(p['reported_absence_reason'],'LEFT HAND');self.assertIsNone(p['absence_category'])
    def test_non_object_json_is_client_error(self):
        client=app.test_client()
        for body in [[],['bad'],None,'bad',23]:
            with self.subTest(body=body):self.assertEqual(client.post('/run',json=body).status_code,400)
    def test_future_season_ui(self):
        html=app.test_client().get('/').data.decode()
        from bs4 import BeautifulSoup
        field=BeautifulSoup(html,'html.parser').select_one('select#season')
        self.assertIsNotNone(field)
        options=field.select('option')
        years=[int(option['value']) for option in options]
        self.assertEqual(years,sorted(years,reverse=True))
        self.assertEqual(min(years),1997)
        self.assertIn(2025,years)
        current=int(field.select_one('option[selected]')['value'])
        self.assertEqual(max(years),current+2)
        self.assertTrue(all('upcoming' in option.text for option in options if int(option['value'])>current))
        self.assertIn('2024–25',field.text)
        self.assertNotIn('{{ default_season }}',html)
    def test_invalid_limits(self):
        for limit in [True,2.5,'abc',0,101]:
            with self.assertRaises(ValueError):collect_dashboard('team','LAL','2025',limit)
if __name__=='__main__':unittest.main()
