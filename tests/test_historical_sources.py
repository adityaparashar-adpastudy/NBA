import json, unittest
from pathlib import Path
from unittest.mock import patch, Mock
import requests
from nba_espn_collector import parse_summary
from nba_official_reports import parse_report, _fetch_report, official_for_game, clean_name
from lakers_test import classify_absence
FIX=Path(__file__).parent/'fixtures/historical'
class HistoricalSources(unittest.TestCase):
    def test_five_actual_historical_report_layouts(self):
        for year, count in [(2018,38),(2019,35),(2020,29),(2021,100),(2022,34)]:
            with self.subTest(year=year):
                report=parse_report((FIX/f'{year}.pdf').read_bytes(),f'{year}.pdf')
                self.assertEqual(len(report['records']),count)
                self.assertTrue(all(r['game_date'].startswith(str(year)) for r in report['records']))
        old=parse_report((FIX/'2018.pdf').read_bytes(),'2018.pdf')['records']
        ilyasova=next(r for r in old if r['player_full_name']=='Ersan Ilyasova')
        self.assertEqual(ilyasova['source_category'],'Injury/Illness')
        self.assertEqual(ilyasova['source_reason'],'Surgery - broken nose')
        self.assertEqual(ilyasova['category'],'injury')
        modern=parse_report((FIX/'2022.pdf').read_bytes(),'2022.pdf')['records']
        davis=next(r for r in modern if r['player_full_name']=='Anthony Davis')
        self.assertEqual(davis['reported_reason'],'Injury/Illness - Right Foot; Stress injury')
    def test_relocations_use_source_franchise_id(self):
        for team,year,name in [('bkn',1997,'New Jersey Nets'),('okc',2002,'Seattle SuperSonics'),('mem',1997,'Vancouver Grizzlies'),('no',1997,'Charlotte Hornets')]:
            path=next(FIX.glob(f'{team}_{year}_*.json'))
            result=parse_summary(json.loads(path.read_text()),team.upper(),path.stem.split('_')[-1])
            self.assertEqual(result['team_name'],name)
            self.assertGreater(len(result['players']),0)
    def test_no_minutes_keeps_game_and_unknown_players(self):
        path=next(FIX.glob('chi_*.json'))
        result=parse_summary(json.loads(path.read_text()),'CHI','400277727')
        self.assertEqual(result['players_entered'],0)
        self.assertEqual(result['participation_unknown'],10)
        self.assertEqual(result['players_dnp'],2)
        self.assertEqual(result['dnp_coverage'],'incomplete')
        self.assertTrue(all(p['minutes'] is None for p in result['players']))
    def test_names_and_respiratory(self):
        self.assertEqual(clean_name('Gilgeous- Alexander, Shai'),'Gilgeous-Alexander, Shai')
        for reason in ['Upper Respiratory Infection','Respiratory']:
            self.assertEqual(classify_absence(reason),'illness')
    def test_transient_retry_and_failure_not_cached(self):
        _fetch_report.cache_clear()
        response=Mock(status_code=200,content=b'%PDF sample')
        with patch('nba_official_reports.requests.get',side_effect=[requests.Timeout(),response]) as get,patch('nba_official_reports.sleep'),patch('nba_official_reports.parse_report',return_value={'records':[]}):
            self.assertEqual(_fetch_report('retry',0),{'records':[]})
            self.assertEqual(get.call_count,2)
        with patch('nba_official_reports.requests.get',side_effect=requests.Timeout()) as get,patch('nba_official_reports.sleep'):
            for _ in range(2):
                with self.assertRaises(requests.Timeout):_fetch_report('failure',0)
            self.assertEqual(get.call_count,6)
    def test_failure_distinguished_from_search_without_match(self):
        with patch('nba_official_reports.fetch_report',side_effect=requests.Timeout()):
            result=official_for_game('2022-12-25T19:30Z','LAL','LAL@DAL')
        self.assertEqual(result['retrieval_status'],'fetch_failed')
        with patch('nba_official_reports.fetch_report',return_value=None):
            result=official_for_game('2022-12-25T19:30Z','LAL','LAL@DAL')
        self.assertEqual(result['retrieval_status'],'no_matching_snapshot')
if __name__=='__main__':unittest.main()
