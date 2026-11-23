import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
from nba_official_reports import parse_report,report_category,enrich_game,official_for_game,snapshot_candidates
from nba_espn_collector import parse_summary
from nba_dashboard import app
DATA=json.loads((Path(__file__).parent/'fixtures/espn_lal_401704628.json').read_text())
class Page:
    mediabox=type('Box',(),{'height':595})()
    rotation=0
    def __init__(self,rows):self.rows=rows
    def extract_text(self,visitor_text=None):
        if not visitor_text:return 'Injury Report: 10/22/24 05:30 PM'
        words=[(200,115,'Matchup'),(264,115,'Team'),(425,115,'Player'),(585,115,'Current'),(666,115,'Reason')]+self.rows
        for x,y,text in words:visitor_text(text,[1,0,0,1,0,0],[1,0,0,1,x,595-y],None,10)
class OfficialTests(unittest.TestCase):
    def sample(self):
        return dict(status='available',report_at='2024-10-22T17:30:00-04:00',source_url='https://ak-static.cms.nba.com/report.pdf',records=[dict(player_full_name='Jarred Vanderbilt',reported_status='Out',reported_reason='Injury/Illness - Right Foot; Injury Recovery',category='injury',report_at='2024-10-22T17:30:00-04:00',source_url='https://ak-static.cms.nba.com/report.pdf')],note='snapshot')
    def test_prefix_is_not_a_mixed_condition(self):
        self.assertEqual(report_category('Injury/Illness - Right Foot; Injury Recovery'),'injury')
        self.assertEqual(report_category('Injury/Illness - Illness'),'illness')
        self.assertEqual(report_category('Injury/Illness'),'unknown')
        self.assertEqual(report_category('G League - Two-Way'),'other')
        self.assertEqual(report_category('Concussion Protocol'),'injury')
    def test_rows_and_wrapped_reason(self):
        page=Page([(24,145,'10/22/2024'),(201,145,'MIN@LAL'),(265,145,'Los Angeles Lakers'),(426,145,'Vanderbilt, Jarred'),(587,145,'Out'),(667,138,'Injury/Illness - Right Foot;'),(667,152,'Injury Recovery'),(426,175,'Wood, Christian'),(587,175,'Out'),(667,175,'Injury/Illness - Right Knee')])
        with patch('nba_official_reports.PdfReader',return_value=type('Reader',(),{'pages':[page]})()):r=parse_report(b'pdf','source')
        self.assertEqual(len(r['records']),2)
        self.assertEqual(r['records'][0]['player_full_name'],'Jarred Vanderbilt')
        self.assertEqual(r['records'][0]['reported_reason'],'Injury/Illness - Right Foot; Injury Recovery')
        self.assertEqual(r['records'][1]['team_code'],'LAL')
    def test_team_suspension_does_not_replace_team_column_heading(self):
        page=Page([(24,145,'10/22/2024'),(201,145,'MIN@LAL'),(265,145,'Los Angeles Lakers'),(426,145,'Butler, Jimmy'),(587,145,'Out'),(667,145,'Team Suspension')])
        with patch('nba_official_reports.PdfReader',return_value=type('Reader',(),{'pages':[page]})()):r=parse_report(b'pdf','source')
        self.assertEqual(r['records'][0]['reported_reason'],'Team Suspension')
        self.assertEqual(r['records'][0]['team_code'],'LAL')
    def test_unrecognized_layout_fails_closed(self):
        with patch('nba_official_reports.PdfReader',return_value=type('Reader',(),{'pages':[Page([])]})()):
            # A valid empty report layout has no player records; game matching remains unavailable.
            r=parse_report(b'pdf','source');self.assertEqual(r['records'],[])
    def test_available_with_dash_reason_is_retained_as_unknown(self):
        page=Page([(24,145,'10/22/2024'),(201,145,'MIN@LAL'),(265,145,'Los Angeles Lakers'),(426,145,'Example, Player'),(587,145,'Available'),(667,145,'-')])
        with patch('nba_official_reports.PdfReader',return_value=type('Reader',(),{'pages':[page]})()):r=parse_report(b'pdf','source')
        self.assertEqual(r['records'][0]['reported_reason'],'-')
        self.assertEqual(r['records'][0]['category'],'unknown')
    def test_unreconciled_reason_fails_closed(self):
        page=Page([(24,145,'10/22/2024'),(201,145,'MIN@LAL'),(265,145,'Los Angeles Lakers'),(426,145,'Example, Player'),(587,145,'Out'),(667,145,'Unexpected report layout')])
        with patch('nba_official_reports.PdfReader',return_value=type('Reader',(),{'pages':[page]})()):
            with self.assertRaisesRegex(ValueError,'do not reconcile'):parse_report(b'pdf','source')
    def test_standalone_concussion_protocol_reason(self):
        page=Page([(24,145,'10/22/2024'),(201,145,'MIN@LAL'),(265,145,'Los Angeles Lakers'),(426,145,'Example, Player'),(587,145,'Out'),(667,145,'Concussion Protocol')])
        with patch('nba_official_reports.PdfReader',return_value=type('Reader',(),{'pages':[page]})()):r=parse_report(b'pdf','source')
        self.assertEqual(r['records'][0]['category'],'injury')
    def test_missing_player_added_to_report_without_fake_boxscore(self):
        m=parse_summary(DATA,'LAL','401704628')
        with patch('nba_official_reports.official_for_game',return_value=self.sample()):r=enrich_game(m,DATA,'LAL')
        self.assertEqual(r['official_report_counts']['injury'],1)
        self.assertEqual(r['players_dnp'],3)
        self.assertEqual(r['official_report']['records'][0]['actual_participation'],'not_listed_in_box_score')
        self.assertIsNone(r['official_report']['records'][0]['player_id'])
    def test_injury_report_player_can_have_played(self):
        report=self.sample();report['records'][0]['player_full_name']='Anthony Davis';report['records'][0]['reported_status']='Questionable'
        with patch('nba_official_reports.official_for_game',return_value=report):r=enrich_game(parse_summary(DATA,'LAL','401704628'),DATA,'LAL')
        record=r['official_report']['records'][0]
        self.assertEqual(record['actual_participation'],'played');self.assertEqual(record['reported_minutes'],'38')
        self.assertEqual(r['official_report_counts']['injury'],1)
    def test_unavailable_is_not_zero(self):
        with patch('nba_official_reports.official_for_game',return_value=dict(status='unavailable',records=[])):
            r=enrich_game(parse_summary(DATA,'LAL','401704628'),DATA,'LAL')
        self.assertIsNone(r['official_report_counts'])
    def test_after_tipoff_report_rejected(self):
        report=dict(report_at='2024-10-22T23:30:00-04:00',matchups=[('2024-10-22','MIN@LAL')],not_submitted=[],records=[])
        with patch('nba_official_reports.fetch_report',return_value=report):r=official_for_game('2024-10-23T02:00Z','LAL','MIN@LAL')
        self.assertEqual(r['status'],'unavailable')
    def test_not_submitted_not_zero(self):
        report=dict(report_at='2024-10-22T17:30:00-04:00',matchups=[('2024-10-22','MIN@LAL')],not_submitted=[('2024-10-22','MIN@LAL','LAL')],records=[])
        with patch('nba_official_reports.fetch_report',return_value=report):r=official_for_game('2024-10-23T02:00Z','LAL','MIN@LAL')
        self.assertEqual(r['status'],'unavailable')
    def test_missing_fetch_is_unavailable(self):
        with patch('nba_official_reports.fetch_report',return_value=None):r=official_for_game('2024-10-23T02:00Z','LAL','MIN@LAL')
        self.assertEqual(r['status'],'unavailable')
    def test_background_job(self):
        from time import sleep
        client=app.test_client()
        with patch('nba_espn_collector.collect_dashboard',return_value=dict(mode='team',games=[],output='')):
            response=client.post('/api/query',json=dict(team='LAL',season='2025'));self.assertEqual(response.status_code,202)
            for _ in range(50):
                job=client.get('/api/jobs/'+response.json['job_id']).json
                if job['status']=='complete':break
                sleep(.01)
        self.assertTrue(job['data']['ok'])
        self.assertEqual(client.get('/api/jobs/does-not-exist').status_code,404)
    def test_background_json_validation(self):
        self.assertEqual(app.test_client().post('/api/query',json=['bad']).status_code,400)
if __name__=='__main__':unittest.main()
