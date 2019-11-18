from mock.mock import MagicMock
import mock

from custom.up_nrhm.reports.block_level_af_report import BlockLevelAFReport
from custom.up_nrhm.reports.block_level_month_report import BlockLevelMonthReport
from custom.up_nrhm.reports.district_functionality_report import DistrictFunctionalityReport
from custom.up_nrhm.tests.utils import UpNrhmTestCase
from custom.up_nrhm.reports.asha_functionality_checklist_report import ASHAFunctionalityChecklistReport
from custom.up_nrhm.reports.asha_facilitators_report import ASHAFacilitatorsReport

RUN_QUERY_VALUE = {
    'hits': {
        'total': 0,
        'hits': []
    },
    'facets': {
        'vaccination_names': {
            'terms': [
                {'term': 'foo', 'count': 10}
            ]
        }
    }
}


class TestASHAFunctionalityChecklistReport(UpNrhmTestCase):

    @mock.patch('corehq.apps.es.es_query.run_query', return_value=RUN_QUERY_VALUE)
    def test_asha_functionality_checklist_report(self, mock_run_query):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'lang': '',
            'sf': '',
            'startdate': '2018-01-01',
            'enddate': '2018-01-31',
            'hierarchy_af': '646eb23165f2f3ee9966b0512efc9494',
            'month': '01',
            'year': '2018',
            'hierarchy_district': 'kaushambi',
            'hierarchy_block': 'Chail',
        }
        asha_functionality_checklist_report = ASHAFunctionalityChecklistReport(request=mock, domain='up-nrhm')
        rows = asha_functionality_checklist_report.rows
        self.assertEqual(
            rows,
            [
                ['', 'Date when cheklist was filled', 'Total no. of ASHAs functional on each tasks'],
                [1, 'Newborn visits within first day of birth in case of home deliveries', 0],
                [2,
                 'Set of home visits for newborn care as specified in the HBNC guidelines (six visits in case '
                 'of Institutional delivery and seven in case of a home delivery)',
                 0],
                [3, 'Attending VHNDs/Promoting immunization', 0], [4, 'Supporting institutional delivery', 0],
                [5, 'Management of childhood illness - especially diarrhea and pneumonia', 0],
                [6, 'Household visits with nutrition counseling', 0],
                [7, 'Fever cases seen/malaria slides made in malaria endemic area', 0],
                [8, 'Acting as DOTS provider', 0], [9, 'Holding or attending village/VHSNC meeting', 0],
                [10,
                 'Successful referral of the IUD, female sterilization or male sterilization cases and/or '
                 'providing OCPs/Condoms',
                 0],
                ['', 'Total of number of tasks on which ASHA reported being functional', ''],
                ['', 'Total number of ASHAs who are functional on at least 60% of the tasks', 0],
                ['', 'Remark', '']
            ]
        )

    @mock.patch('corehq.apps.es.es_query.run_query', return_value=RUN_QUERY_VALUE)
    def test_asha_facilitators_report(self, mock_run_query):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'lang': '',
            'sf': 'sf2',
            'startdate': '2018-01-01',
            'enddate': '2018-01-31',
            'hierarchy_af': '646eb23165f2f3ee9966b0512efc9494',
            'month': '01',
            'year': '2018',
        }
        asha_facilitators_report = ASHAFacilitatorsReport(request=mock, domain='up-nrhm')
        rows = asha_facilitators_report.rows
        expected = (
            [
                [
                    'Newborn visits within first day of birth in case of home deliveries', '--',
                    {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Set of home visits for newborn care as specified in the HBNC guidelines<br/>(six visits '
                    'in case of Institutional delivery and seven in case of a home delivery)',
                    '--', {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Attending VHNDs/Promoting immunization', '--', {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Supporting institutional delivery', '--', {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Management of childhood illness - especially diarrhea and pneumonia', '--',
                    {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Household visits with nutrition counseling', '--', {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Fever cases seen/malaria slides made in malaria endemic area', '--',
                    {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Acting as DOTS provider', '--', {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Holding or attending village/VHSNC meeting', '--', {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    'Successful referral of the IUD, female sterilization or male sterilization cases and/or '
                    'providing OCPs/Condoms',
                    '--', {'sort_key': 17, 'html': 17}, ''
                ],
                [
                    '<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                    {'sort_key': 0.0, 'html': '0/0 (0%)'},
                    {'sort_key': 17, 'html': 17},
                    ''
                ]
            ], 17, 0
        )
        self.assertEqual(len(rows), len(expected))
        self.assertEqual(len(rows[0]), len(expected[0]))
        for i in range(len(rows[0])):
            self.assertEqual(len(rows[0][i]), len(expected[0][i]))
            for record in expected[0][i]:
                self.assertIn(record, rows[0][i])

    @mock.patch('corehq.apps.es.es_query.run_query', return_value=RUN_QUERY_VALUE)
    def test_block_level_month_report(self, mock_run_query):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'lang': '',
            'sf': 'sf3',
            'startdate': '2018-01-01',
            'enddate': '2018-01-31',
            'hierarchy_af': '646eb23165f2f3ee9966b0512efc9494',
            'month': '01',
            'year': '2018',
        }
        block_level_month_report = BlockLevelMonthReport(request=mock, domain='up-nrhm')
        rows = block_level_month_report.rows
        expected = (
            [
                [
                    'Newborn visits within first day of birth in case of home deliveries',
                    {'sort_key': 1, 'html': 1}, '--', '--', {'sort_key': '0', 'html': '0'}
                ],
                [
                    'Set of home visits for newborn care as specified in the HBNC guidelines<br/>'
                    '(six visits in case of Institutional delivery and seven in case of a home delivery)',
                    {'sort_key': 10, 'html': 10}, '--', '--', {'sort_key': '3', 'html': '3'}
                ],
                [
                    'Attending VHNDs/Promoting immunization',
                    {'sort_key': 14, 'html': 14}, '--', '--', {'sort_key': '5', 'html': '5'}
                ],
                [
                    'Supporting institutional delivery',
                    {'sort_key': 14, 'html': 14}, '--', '--', {'sort_key': '5', 'html': '5'}
                ],
                [
                    'Management of childhood illness - especially diarrhea and pneumonia',
                    {'sort_key': 11, 'html': 11}, '--', '--', {'sort_key': '4', 'html': '4'}
                ],
                [
                    'Household visits with nutrition counseling',
                    {'sort_key': 5, 'html': 5}, '--', '--', {'sort_key': '2', 'html': '2'}
                ],
                [
                    'Fever cases seen/malaria slides made in malaria endemic area',
                    {'sort_key': 0, 'html': 0}, '--', '--', {'sort_key': '0', 'html': '0'}
                ],
                [
                    'Acting as DOTS provider',
                    {'sort_key': 0, 'html': 0}, '--', '--', {'sort_key': '0', 'html': '0'}
                ],
                [
                    'Holding or attending village/VHSNC meeting',
                    {'sort_key': 0, 'html': 0}, '--', '--', {'sort_key': '0', 'html': '0'}
                ], [
                    'Successful referral of the IUD, female sterilization or male sterilization cases '
                    'and/or providing OCPs/Condoms',
                    {'sort_key': 14, 'html': 14}, '--', '--', {'sort_key': '5', 'html': '5'}
                ],
                [
                    '<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                    {'sort_key': 86.66666666666667, 'html': '13/15 (86%)'}, {'sort_key': 0.0, 'html': '0/0 (0%)'},
                    {'sort_key': 0.0, 'html': '0/0 (0%)'}, {'sort_key': 28.88888888888889, 'html': '4/15 (28%)'}
                ],
                [
                    '<b>Total number of ASHAs who did not report/not known</b>',
                    {'sort_key': 17, 'html': 17}, {'sort_key': 17, 'html': 17},
                    {'sort_key': 2, 'html': 2}, {'sort_key': '12', 'html': '12'}
                ]
            ], 17
        )

        self.assertEqual(len(rows), len(expected))
        self.assertEqual(len(rows[0]), len(expected[0]))
        for i in range(len(rows[0])):
            self.assertEqual(len(rows[0][i]), len(expected[0][i]))
            for record in expected[0][i]:
                self.assertIn(record, rows[0][i])

    @mock.patch('corehq.apps.es.es_query.run_query', return_value=RUN_QUERY_VALUE)
    def test_block_level_af_report(self, mock_run_query):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'lang': '',
            'sf': 'sf4',
            'startdate': '2018-01-01',
            'enddate': '2018-01-31',
            'hierarchy_af': '646eb23165f2f3ee9966b0512efc9494',
            'month': '01',
            'year': '2018',
            'hierarchy_district': 'kaushambi',
            'hierarchy_block': 'Chail',
        }
        block_level_af_report = BlockLevelAFReport(request=mock, domain='up-nrhm')
        rows = block_level_af_report.rows
        expected = (
            [
                [
                    'Newborn visits within first day of birth in case of home deliveries',
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '2', 'html': '2'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '1', 'html': '1'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '1', 'html': '1'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': 4.0, 'html': 4.0}
                ],
                [
                    'Set of home visits for newborn care as specified in the HBNC guidelines<br/>'
                    '(six visits in case of Institutional delivery and seven in case of a home delivery)',
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '3', 'html': '3'},
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '3', 'html': '3'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': '2', 'html': '2'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': 32.0, 'html': 32.0}
                ],
                [
                    'Attending VHNDs/Promoting immunization',
                    {'sort_key': '6', 'html': '6'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '5', 'html': '5'},
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '5', 'html': '5'}, {'sort_key': 43.0, 'html': 43.0}
                ],
                [
                    'Supporting institutional delivery',
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '1', 'html': '1'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '3', 'html': '3'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': 32.0, 'html': 32.0}
                ],
                [
                    'Management of childhood illness - especially diarrhea and pneumonia',
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '3', 'html': '3'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': 34.0, 'html': 34.0}
                ],
                [
                    'Household visits with nutrition counseling',
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': '3', 'html': '3'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': '3', 'html': '3'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': '3', 'html': '3'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': 30.0, 'html': 30.0}
                ],
                [
                    'Fever cases seen/malaria slides made in malaria endemic area',
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': 0.0, 'html': 0.0}],
                [
                    'Acting as DOTS provider',
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': 0.0, 'html': 0.0}
                ],
                [
                    'Holding or attending village/VHSNC meeting',
                    {'sort_key': '1', 'html': '1'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '0', 'html': '0'},
                    {'sort_key': '3', 'html': '3'}, {'sort_key': 12.0, 'html': 12.0}
                ],
                [
                    'Successful referral of the IUD, female sterilization or male '
                    'sterilization cases and/or providing OCPs/Condoms',
                    {'sort_key': '6', 'html': '6'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '5', 'html': '5'},
                    {'sort_key': '5', 'html': '5'}, {'sort_key': '4', 'html': '4'},
                    {'sort_key': '4', 'html': '4'}, {'sort_key': 41.0, 'html': 41.0}
                ],
                [
                    '<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                    {'sort_key': 29.629629629629626, 'html': '5/18 (29%)'},
                    {'sort_key': 30.76923076923077, 'html': '4/13 (30%)'},
                    {'sort_key': 28.88888888888889, 'html': '4/15 (28%)'},
                    {'sort_key': 33.33333333333333, 'html': '4/13 (33%)'},
                    {'sort_key': 33.333333333333336, 'html': '4/14 (33%)'},
                    {'sort_key': 27.083333333333332, 'html': '4/16 (27%)'},
                    {'sort_key': 27.083333333333332, 'html': '4/16 (27%)'},
                    {'sort_key': 30.555555555555554, 'html': '3/12 (30%)'},
                    {'sort_key': 30.952380952380953, 'html': '4/14 (30%)'},
                    {'sort_key': 27, 'html': '36/131 (27%)'}
                ],
                [
                    '<b>Total number of ASHAs who did not report/not known</b>',
                    {'sort_key': '12', 'html': '12'}, {'sort_key': '11', 'html': '11'},
                    {'sort_key': '11', 'html': '11'}, {'sort_key': '11', 'html': '11'},
                    {'sort_key': '10', 'html': '10'}, {'sort_key': '12', 'html': '12'},
                    {'sort_key': '12', 'html': '12'}, {'sort_key': '10', 'html': '10'},
                    {'sort_key': '10', 'html': '10'}, {'sort_key': 99.0, 'html': 99.0}
                ],
                [
                    '<b>Total Number of ASHAs under each Facilitator</b>',
                    {'sort_key': 18, 'html': 18}, {'sort_key': 15, 'html': 15},
                    {'sort_key': 16, 'html': 16}, {'sort_key': 15, 'html': 15},
                    {'sort_key': 15, 'html': 15}, {'sort_key': 17, 'html': 17},
                    {'sort_key': 17, 'html': 17}, {'sort_key': 14, 'html': 14},
                    {'sort_key': 15, 'html': 15}, {'sort_key': 142, 'html': 142}
                ]
            ], 142
        )

        self.assertEqual(len(rows), len(expected))
        self.assertEqual(len(rows[0]), len(expected[0]))
        for i in range(len(rows[0])):
            self.assertEqual(len(rows[0][i]), len(expected[0][i]))
            for record in expected[0][i]:
                self.assertIn(record, rows[0][i])

    @mock.patch('corehq.apps.es.es_query.run_query', return_value=RUN_QUERY_VALUE)
    def test_district_functionality_report(self, mock_run_query):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'lang': '',
            'sf': 'sf5',
            'startdate': '2018-01-01',
            'enddate': '2018-01-31',
            'hierarchy_af': '646eb23165f2f3ee9966b0512efc9494',
            'month': '01',
            'year': '2018',
            'hierarchy_district': 'kaushambi',
            'hierarchy_block': 'Chail',
        }
        district_functionality_report = DistrictFunctionalityReport(request=mock, domain='up-nrhm')
        rows = district_functionality_report.rows
        expected = (
            [
                [
                    'Newborn visits within first day of birth in case of home deliveries',
                    {'sort_key': '2.8%', 'html': '2.8%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '2.3%', 'html': '2.3%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '2.4%', 'html': '2.4%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '2.6%', 'html': '2.6%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '3.0%', 'html': '3.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '3.2%', 'html': '3.2%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '4.7%', 'html': '4.7%'}, {'sort_key': 'D', 'html': 'D'}
                ],
                [
                    'Set of home visits for newborn care as specified in the HBNC guidelines<br/>'
                    '(six visits in case of Institutional delivery and seven in case of a home delivery)',
                    {'sort_key': '22.5%', 'html': '22.5%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '20.9%', 'html': '20.9%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '17.2%', 'html': '17.2%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '21.0%', 'html': '21.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '19.6%', 'html': '19.6%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '21.6%', 'html': '21.6%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '19.0%', 'html': '19.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '20.2%', 'html': '20.2%'}, {'sort_key': 'D', 'html': 'D'}
                ],
                [
                    'Attending VHNDs/Promoting immunization',
                    {'sort_key': '30.3%', 'html': '30.3%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '29.5%', 'html': '29.5%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '25.3%', 'html': '25.3%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '29.8%', 'html': '29.8%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '29.6%', 'html': '29.6%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '29.1%', 'html': '29.1%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '28.6%', 'html': '28.6%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '27.1%', 'html': '27.1%'}, {'sort_key': 'C', 'html': 'C'}
                ],
                [
                    'Supporting institutional delivery',
                    {'sort_key': '22.5%', 'html': '22.5%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '27.1%', 'html': '27.1%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '20.2%', 'html': '20.2%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '22.6%', 'html': '22.6%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '24.9%', 'html': '24.9%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '24.6%', 'html': '24.6%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '23.0%', 'html': '23.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '17.8%', 'html': '17.8%'}, {'sort_key': 'D', 'html': 'D'}
                ],
                [
                    'Management of childhood illness - especially diarrhea and pneumonia',
                    {'sort_key': '23.9%', 'html': '23.9%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '18.6%', 'html': '18.6%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '27.3%', 'html': '27.3%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '20.2%', 'html': '20.2%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '17.5%', 'html': '17.5%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '10.4%', 'html': '10.4%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '24.6%', 'html': '24.6%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '22.5%', 'html': '22.5%'}, {'sort_key': 'D', 'html': 'D'}
                ],
                [
                    'Household visits with nutrition counseling',
                    {'sort_key': '21.1%', 'html': '21.1%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '9.3%', 'html': '9.3%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '13.1%', 'html': '13.1%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '9.0%', 'html': '9.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.7%', 'html': '0.7%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '15.5%', 'html': '15.5%'}, {'sort_key': 'D', 'html': 'D'}
                ],
                [
                    'Fever cases seen/malaria slides made in malaria endemic area',
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '1.0%', 'html': '1.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'}
                ],
                [
                    'Acting as DOTS provider',
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '8.5%', 'html': '8.5%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '5.1%', 'html': '5.1%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '5.6%', 'html': '5.6%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '4.2%', 'html': '4.2%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '2.2%', 'html': '2.2%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '6.2%', 'html': '6.2%'}, {'sort_key': 'D', 'html': 'D'}
                ],
                [
                    'Holding or attending village/VHSNC meeting',
                    {'sort_key': '8.5%', 'html': '8.5%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '2.3%', 'html': '2.3%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '7.1%', 'html': '7.1%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '8.9%', 'html': '8.9%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '9.0%', 'html': '9.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '4.0%', 'html': '4.0%'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': '12.4%', 'html': '12.4%'}, {'sort_key': 'D', 'html': 'D'}
                ],
                [
                    'Successful referral of the IUD, female sterilization or male sterilization cases '
                    'and/or providing OCPs/Condoms',
                    {'sort_key': '28.9%', 'html': '28.9%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '31.0%', 'html': '31.0%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '29.3%', 'html': '29.3%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '28.2%', 'html': '28.2%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '25.9%', 'html': '25.9%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '28.4%', 'html': '28.4%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '27.0%', 'html': '27.0%'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': '27.1%', 'html': '27.1%'}, {'sort_key': 'C', 'html': 'C'}
                ],
                [
                    '<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                    {'sort_key': 27, 'html': '36/131 (27%)'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': 27, 'html': '34/122 (27%)'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': 24, 'html': '22/91 (24%)'}, {'sort_key': 'D', 'html': 'D'},
                    {'sort_key': 26, 'html': '31/116 (26%)'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': 26, 'html': '46/175 (26%)'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': 28, 'html': '34/121 (28%)'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': 27, 'html': '31/111 (27%)'}, {'sort_key': 'C', 'html': 'C'},
                    {'sort_key': 26, 'html': '30/114 (26%)'}, {'sort_key': 'C', 'html': 'C'}
                ]
            ], 0
        )

        self.assertEqual(len(rows), len(expected))
        self.assertEqual(len(rows[0]), len(expected[0]))
        for i in range(len(rows[0])):
            self.assertEqual(len(rows[0][i]), len(expected[0][i]))
            for record in expected[0][i]:
                self.assertIn(record, rows[0][i])
