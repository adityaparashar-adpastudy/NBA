import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup
from lakers_test import classify_absence, parse_boxscore, collect_dashboard
from nba_dashboard import app

def fixture():
    reasons = ['Did Not Play', 'Did Not Play — Left ankle sprain', 'Did Not Dress — Illness', "Did Not Play — Coach’s Decision", 'Injury/Illness', None, '<script>alert(1)</script>']
    rows = ['<tr><th data-stat="player" data-append-csv="played01">Played</th><td data-stat="mp">0:45</td></tr>', '<tr><th data-stat="player">Team Totals</th><td data-stat="mp">240:00</td></tr>']
    for i, reason in enumerate(reasons):
        cell = '<td data-stat="reason">'+reason.replace('<','&lt;').replace('>','&gt;')+'</td>' if reason else '<td data-stat="mp"></td>'
        rows.append(f'<tr><th data-stat="player" data-append-csv="p{i}">Player {i}</th>{cell}</tr>')
    return BeautifulSoup('<table id="box-LAL-game-basic"><tbody>'+''.join(rows)+'</tbody></table>', 'lxml')

class AbsenceTests(unittest.TestCase):
    def test_classifications(self):
        for reason, expected in [('DNP','unknown'),('Inactive','unknown'),('Not With Team','other'),('Personal reasons','other'),('Right knee soreness','injury'),('Flu','illness'),('Injury/Illness','unknown'),('Rest / ankle injury','unknown'),(None,'unknown')]:
            with self.subTest(reason=reason): self.assertEqual(classify_absence(reason), expected)
    def test_source_preservation_and_counts(self):
        m = parse_boxscore(fixture(), '202410220LAL', 'LAL')
        self.assertEqual(m['absence_counts'],dict(injury=1,illness=1,other=1,unknown=4))
        self.assertEqual(m['players_dnp'],7)
        self.assertEqual(m['players_entered'],1)
        self.assertEqual(m['minutes_played'],0.8)
        self.assertEqual(m['players'][2]['reported_absence_reason'],'Did Not Play — Left ankle sprain')
        self.assertEqual(m['players'][-1]['reported_absence_reason'],'<script>alert(1)</script>')
        self.assertIsNone(m['players'][-2]['reported_absence_reason'])
    def test_missing_boxscore_is_error(self):
        with self.assertRaises(ValueError): parse_boxscore(BeautifulSoup('', 'lxml'), '202410220LAL','LAL')
    def test_commented_table(self):
        soup=BeautifulSoup('<!--'+str(fixture().table)+'-->','lxml')
        self.assertEqual(parse_boxscore(soup,'202410220LAL','LAL')['players_dnp'],7)
    def test_route_returns_player_records(self):
        with patch('lakers_test.get_soup',return_value=fixture()):
            response=app.test_client().post('/run',json=dict(mode='game',team='LAL',game_id='202410220LAL'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['metrics']['absence_counts']['injury'],1)
        self.assertEqual(len(response.json['metrics']['players']),8)
    def test_source_failure_not_zero(self):
        with patch('lakers_test.get_soup',side_effect=RuntimeError('source failed')):
            response=app.test_client().post('/run',json=dict(mode='game',team='LAL',game_id='202410220LAL'))
        self.assertEqual(response.status_code,502)
        self.assertFalse(response.json['ok'])
        self.assertNotIn('metrics',response.json)
    def test_partial_collection_is_explicit(self):
        import pandas as pd
        log=pd.DataFrame([dict(game_id='202410220LAL',Date='2024-10-22'),dict(game_id='202410240LAL',Date='2024-10-24')])
        m=parse_boxscore(fixture(),'202410220LAL','LAL')
        with patch('lakers_test.get_game_log',return_value=log),patch('lakers_test.get_game_metrics',side_effect=[m,ValueError('unavailable')]):
            result=collect_dashboard('team','LAL','2025',2)
        self.assertEqual(len(result['games']),1)
        self.assertEqual(result['requested_games'],2)
        self.assertEqual(len(result['warnings']),1)
    def test_no_games_is_error(self):
        import pandas as pd
        with patch('lakers_test.get_game_log',return_value=pd.DataFrame()):
            with self.assertRaises(ValueError): collect_dashboard('team','LAL','2025',2)
    def test_home_page(self):
        response=app.test_client().get('/')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'player absence reasons', response.data)
        self.assertIn(b'escapeHtml(p.reported_absence_reason',response.data)

if __name__=='__main__': unittest.main()
