"""Regression tests from the supplied 2023–26 NBA validation findings."""
import copy,csv,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import requests
from nba_official_reports import parse_report,report_category
from nba_espn_collector import _fetch,collect_dashboard
from lakers_test import classify_absence
FIXTURES=Path(__file__).parent/'fixtures'

class PdfRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports={p.name:parse_report(p.read_bytes(),p.name) for p in (FIXTURES/'official_reason_rows').glob('*.pdf')}
    def reason(self,pdf,player):
        records=[r for r in self.reports[pdf]['records'] if r['player_full_name']==player]
        self.assertEqual(len(records),1);return records[0]['reported_reason']
    def test_all_ten_supplied_mismatches(self):
        cases=[('2023-10-28_08PM','Jaylin Williams','Injury/Illness - Right Hamstring; Strain'),('2023-10-28_08PM','Kenrich Williams','Injury/Illness - Low Back; Spasms'),('2023-10-28_09PM','Bradley Beal','Injury/Illness - Low Back; Spasms'),('2023-10-28_09PM','Devin Booker','Injury/Illness - Left Ankle; Sprain'),('2023-10-28_09PM','Damion Lee','Injury/Illness - Right Meniscus; Surgery'),('2025-01-27_06PM','Jimmy Butler','Team Suspension'),('2025-10-24_07PM','Tyler Herro','Injury/Illness - Left Ankle; Surgery'),('2025-10-24_07PM','Kasparas Jakucionis','Injury/Illness - Right Groin; Strain'),('2025-10-24_07PM','Terry Rozier','Not With Team'),('2025-10-24_07PM',"Kel'el Ware",'Injury/Illness - Left Ankle; Sprain')]
        for pdf,player,reason in cases:
            with self.subTest(pdf=pdf,player=player):self.assertEqual(self.reason('Injury-Report_'+pdf+'.pdf',player),reason)
    def test_continuation_crosses_page_without_shifting_next_row(self):
        pdf='Injury-Report_2023-10-28_09PM.pdf'
        self.assertEqual(self.reason(pdf,'Jock Landale'),'Injury/Illness - Head; Concussion Protocol')
        self.assertEqual(self.reason(pdf,'Victor Oladipo'),'Injury/Illness - Left Patellar Tendon; Repair')
    def test_prefix_on_second_line_is_not_a_second_player(self):
        self.assertEqual(self.reason('Injury-Report_2025-01-27_06PM.pdf','Goga Bitadze'),'Injury/Illness - Concussion Protocol; Concussion Protocol')
    def test_all_fixture_rows_remain_present(self):
        self.assertEqual({p:len(r['records']) for p,r in self.reports.items()},{'Injury-Report_2023-10-28_08PM.pdf':77,'Injury-Report_2023-10-28_09PM.pdf':77,'Injury-Report_2025-01-27_06PM.pdf':141,'Injury-Report_2025-10-24_07PM.pdf':98})

class ClassificationReviewTests(unittest.TestCase):
    def test_every_supplied_classification_case(self):
        with (FIXTURES/'nba_classification_review.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),113)
        for row in rows:
            # This row explicitly includes both injury and illness. Retain
            # unknown rather than accepting the suggested injury-only label.
            expected='unknown' if row['reason']=='Injury/Illness - Right Index Finger; Sprain / Illness' else row['suggested']
            with self.subTest(reason=row['reason'],player=row['player']):
                self.assertEqual(report_category(row['reason']),expected)
                self.assertEqual(classify_absence(row['reason']),expected)
    def test_additional_reasons_found_in_all_team_pdf_recheck(self):
        expected={
            'Injury/Illness - Right Fifth Metatarsal; Repair':'injury',
            'Injury/Illness - Left Tibial; Stress Reaction':'injury',
            'Injury/Illness - Right Facet; Inflammation':'injury',
            'Injury/Illness - Core; Tightness':'injury',
            'Injury/Illness - Right Patella; Tendonopathy':'injury',
            'Injury/Illness - Head; Laceration':'injury',
            'Injury/Illness - Post traumatic; Headache':'injury',
            'Injury/Illness - Disc; Irritation':'injury',
            'Injury/Illness - Lumbar; Stress Reaction':'injury',
            'Injury/Illness - N/A; Strep Throat':'illness',
            'Injury/Illness - N/a; Strep throat':'illness'}
        for reason,category in expected.items():
            with self.subTest(reason=reason):
                self.assertEqual(report_category(reason),category)
                self.assertEqual(classify_absence(reason),category)
    def test_explicit_head_illness_is_not_relabelled_as_injury(self):
        self.assertEqual(report_category('Injury/Illness - Head; Illness'),'illness')
    def test_equipment_and_mixed_conditions_do_not_become_confirmed_injuries(self):
        for reason in ['Injury/Illness - N/a; Facemask','Return to Competition Reconditioning','-',
                       'Injury/Illness - Lower Back; Injury Mangement/Illness','Headache',
                       'Injury/Illness - Lumbar; Illness']:
            with self.subTest(reason=reason):self.assertEqual(report_category(reason),'unknown')

    def test_source_prefix_and_whitespace_do_not_change_category(self):
        for reason in ['Left Sciatic Nerve','Right Sciatica','Left Plantar','Left Patellofemoral','Posterior Tibialis Tendon','CORNEAL ABRASION','VIRUS']:
            expected=classify_absence(reason)
            self.assertEqual(report_category('Injury/Illness - '+reason),expected)
            self.assertEqual(classify_absence('Injury/Illness - '+reason.upper().replace(' ','  ')),expected)
        self.assertEqual(classify_absence('VIRUS'),'illness')
        for reason in ['Injury/Illness','DNP','Injury/Illness - Flu / Ankle Sprain']:
            self.assertEqual(classify_absence(reason),'unknown')

class RetryCoverageTests(unittest.TestCase):
    def setUp(self):_fetch.cache_clear()
    def tearDown(self):_fetch.cache_clear()
    def response(self,status=200):
        response=Mock();response.json.return_value={'events':[]}
        if status!=200:
            raw=requests.Response();raw.status_code=status
            response.raise_for_status.side_effect=requests.HTTPError(response=raw)
        return response
    def test_transient_connection_error_recovers_and_success_is_cached(self):
        with patch('nba_espn_collector.requests.get',side_effect=[requests.ConnectionError('transient'),self.response()]) as get,patch('nba_espn_collector.sleep'):
            self.assertEqual(_fetch('teams/phx/schedule',1),{'events':[]})
            self.assertEqual(_fetch('teams/phx/schedule',1),{'events':[]})
            self.assertEqual(get.call_count,2)
    def test_throttling_and_server_errors_are_bounded_retries(self):
        for status in [429,502,503]:
            _fetch.cache_clear()
            with patch('nba_espn_collector.requests.get',side_effect=[self.response(status),self.response(status),self.response()]) as get,patch('nba_espn_collector.sleep'):
                self.assertEqual(_fetch('teams/phx/schedule',1),{'events':[]});self.assertEqual(get.call_count,3)
    def test_permanent_errors_do_not_retry(self):
        with patch('nba_espn_collector.requests.get',return_value=self.response(404)) as get,patch('nba_espn_collector.sleep') as sleep:
            with self.assertRaises(requests.HTTPError):_fetch('teams/phx/schedule',1)
            self.assertEqual(get.call_count,1);sleep.assert_not_called()
    def test_exhausted_failures_are_not_cached(self):
        with patch('nba_espn_collector.requests.get',side_effect=[requests.Timeout('source')]*3+[self.response()]) as get,patch('nba_espn_collector.sleep'):
            with self.assertRaises(requests.Timeout):_fetch('teams/phx/schedule',1)
            self.assertEqual(_fetch('teams/phx/schedule',1),{'events':[]});self.assertEqual(get.call_count,4)
    def test_partial_sample_and_full_schedule_have_separate_counts(self):
        events=[{'id':str(i)} for i in range(82)]
        def game(gid,team):
            if gid=='1':raise requests.ConnectionError('exhausted')
            return {'players':[],'official_report':{'status':'unavailable'}}
        with patch('nba_espn_collector.schedule',return_value=events),patch('nba_espn_collector.game',side_effect=game):
            for mode in ['team','roster']:
                result=collect_dashboard(mode,'PHO','2024',5)
                self.assertEqual(result['scheduled_completed_games'],82);self.assertEqual(result['requested_games'],5)
                self.assertEqual(result['collected_games'],4);self.assertEqual(result['missing_games'],1);self.assertEqual(result['missing_game_ids'],['1'])

if __name__=='__main__':unittest.main()
