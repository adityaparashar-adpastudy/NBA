import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from nba_espn_collector import parse_summary,collect_dashboard,normalize
from nba_dashboard import app
DATA=json.loads((Path(__file__).parent/'fixtures/espn_lal_401704628.json').read_text())
class ESPNTests(unittest.TestCase):
    def test_retained_live_source(self):
        m=parse_summary(DATA,'LAL','401704628')
        self.assertEqual(m['date'],'2024-10-22')
        self.assertEqual(m['date_timezone'],'America/Los_Angeles')
        self.assertEqual(m['absence_counts'],dict(injury=0,illness=0,other=3,unknown=0))
        self.assertEqual(m['players_entered'],10)
        self.assertEqual(m['minutes_played'],240)
        self.assertEqual(m['wl'],'W')
        self.assertTrue(all(p['reported_absence_reason'] is None for p in m['players'] if p['played']))
    def test_explicit_and_ambiguous_reasons(self):
        d=copy.deepcopy(DATA)
        rows=d['boxscore']['players'][1]['statistics'][0]['athletes']
        for row,reason in zip([r for r in rows if r['didNotPlay']],['LEFT ANKLE SPRAIN','ILLNESS','INJURY/ILLNESS']):row['reason']=reason
        m=parse_summary(d,'LAL','401704628')
        self.assertEqual(m['absence_counts'],dict(injury=1,illness=1,other=0,unknown=1))
        self.assertEqual(m['players'][-1]['reported_absence_reason'],'INJURY/ILLNESS')
    def test_unknown_reason(self):
        d=copy.deepcopy(DATA)
        for b in d['boxscore']['players']:
            for r in b['statistics'][0]['athletes']:
                if r['didNotPlay']:r.pop('reason',None)
        self.assertEqual(parse_summary(d,'LAL','401704628')['absence_counts']['unknown'],3)
    def test_unfinished_game(self):
        d=copy.deepcopy(DATA);d['header']['competitions'][0]['status']['type']['completed']=False
        with self.assertRaises(ValueError):parse_summary(d,'LAL','401704628')
    def test_missing_minutes_does_not_become_absence(self):
        d=copy.deepcopy(DATA);d['boxscore']['players'][1]['statistics'][0]['athletes'][0]['stats']=[]
        m=parse_summary(d,'LAL','401704628')
        self.assertEqual(m['participation_unknown'],1)
        self.assertEqual(m['players_entered'],9)
        self.assertEqual(m['players_dnp'],3)
        self.assertIsNone(m['players'][0]['played'])
        self.assertIsNone(m['players'][0]['absence_category'])
    def test_game_api(self):
        with patch('nba_espn_collector.fetch',return_value=DATA):
            r=app.test_client().post('/run',json=dict(mode='game',team='LAL',season='2025',game_id='401704628'))
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['metrics']['players_dnp'],3)
    def test_partial_collection(self):
        with patch('nba_espn_collector.schedule',return_value=[{'id':'1'},{'id':'2'}]),patch('nba_espn_collector.game',side_effect=[{'players':[]},ValueError('no boxscore')]):
            result=collect_dashboard('team','LAL','2025',2)
        self.assertEqual(len(result['games']),1);self.assertEqual(result['requested_games'],2);self.assertEqual(len(result['warnings']),1)
    def test_aliases(self):
        self.assertEqual(normalize('GSW'),'GS');self.assertEqual(normalize('BRK'),'BKN')
    def test_all_dropdown_team_codes(self):
        import re
        from nba_dashboard import HTML
        options = re.search(r'<select id="team">(.*?)</select>', HTML, re.S).group(1)
        codes = re.findall(r'value="([A-Z]+)"', options)
        self.assertEqual(len(codes), 30)
        self.assertEqual(len({normalize(code) for code in codes}), 30)
        self.assertEqual(normalize('WAS'),'WSH')
    def test_overtime(self):
        d=copy.deepcopy(DATA)
        for c in d['header']['competitions'][0]['competitors']:c['linescores'].append({'displayValue':'12'})
        self.assertEqual(parse_summary(d,'LAL','401704628')['minutes_played'],265)
if __name__=='__main__':unittest.main()
