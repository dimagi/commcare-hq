# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

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
        self.assertEqual(
            rows,
            (
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
                        {'sort_key': 0.0, 'html': '0/17 (0%)'}, {'sort_key': 17, 'html': 17}, ''
                    ]
                ], 17, 0
            )
        )

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
        self.assertEqual(
            rows,
            (
                [
                    ['Newborn visits within first day of birth in case of home deliveries',
                     {'sort_key': 1, 'html': 1}, '--', '--', {'sort_key': '0', 'html': '0'}
                     ],
                    [
                        'Set of home visits for newborn care as specified in the HBNC guidelines<br/>(six visits '
                        'in case of Institutional delivery and seven in case of a home delivery)',
                        {'sort_key': 8, 'html': 8}, '--', '--', {'sort_key': '3', 'html': '3'}
                    ],
                    [
                        'Attending VHNDs/Promoting immunization', {'sort_key': 12, 'html': 12}, '--', '--',
                        {'sort_key': '4', 'html': '4'}
                    ],
                    [
                        'Supporting institutional delivery', {'sort_key': 12, 'html': 12}, '--', '--',
                        {'sort_key': '4', 'html': '4'}
                    ],
                    [
                        'Management of childhood illness - especially diarrhea and pneumonia',
                        {'sort_key': 9, 'html': 9}, '--', '--', {'sort_key': '3', 'html': '3'}
                    ],
                    [
                        'Household visits with nutrition counseling', {'sort_key': 4, 'html': 4}, '--',
                        '--',
                        {'sort_key': '1', 'html': '1'}
                    ],
                    [
                        'Fever cases seen/malaria slides made in malaria endemic area',
                        {'sort_key': 0, 'html': 0},
                        '--', '--', {'sort_key': '0', 'html': '0'}
                    ],
                    [
                        'Acting as DOTS provider', {'sort_key': 0, 'html': 0}, '--', '--',
                        {'sort_key': '0', 'html': '0'}
                    ],
                    [
                        'Holding or attending village/VHSNC meeting', {'sort_key': 0, 'html': 0}, '--',
                        '--',
                        {'sort_key': '0', 'html': '0'}
                    ],
                    [
                        'Successful referral of the IUD, female sterilization or male sterilization cases '
                        'and/or providing OCPs/Condoms',
                        {'sort_key': 12, 'html': 12}, '--', '--', {'sort_key': '4', 'html': '4'}
                    ],
                    [
                        '<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                        {'sort_key': 64.70588235294117, 'html': '11/17 (64%)'},
                        {'sort_key': 0.0, 'html': '0/17 (0%)'}, {'sort_key': 0.0, 'html': '0/17 (0%)'},
                        {'sort_key': 21.56862745098039, 'html': '3/17 (21%)'}
                    ],
                    [
                        '<b>Total number of ASHAs who did not report/not known</b>',
                        {'sort_key': 17, 'html': 17},
                        {'sort_key': 17, 'html': 17}, {'sort_key': 4, 'html': 4},
                        {'sort_key': '13', 'html': '13'}
                    ]
                ], 17)
        )

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
        self.assertEqual(
            rows,
            (
                [
                    [
                        'Newborn visits within first day of birth in case of home deliveries',
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '2', 'html': '2'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': 2.0, 'html': 2.0}
                    ],
                    [
                        'Set of home visits for newborn care as specified in the HBNC guidelines<br/>(six visits '
                        'in case of Institutional delivery and seven in case of a home delivery)',
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '2', 'html': '2'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '2', 'html': '2'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '2', 'html': '2'},
                        {'sort_key': '2', 'html': '2'}, {'sort_key': 26.0, 'html': 26.0}
                    ],
                    [
                        'Attending VHNDs/Promoting immunization', {'sort_key': '5', 'html': '5'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '5', 'html': '5'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '5', 'html': '5'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': 38.0, 'html': 38.0}
                    ],
                    [
                        'Supporting institutional delivery', {'sort_key': '4', 'html': '4'},
                        {'sort_key': '1', 'html': '1'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '3', 'html': '3'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '3', 'html': '3'},
                        {'sort_key': 29.0, 'html': 29.0}
                    ],
                    [
                        'Management of childhood illness - especially diarrhea and pneumonia',
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '3', 'html': '3'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '3', 'html': '3'},
                        {'sort_key': '2', 'html': '2'}, {'sort_key': 30.0, 'html': 30.0}
                    ],
                    [
                        'Household visits with nutrition counseling', {'sort_key': '3', 'html': '3'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '2', 'html': '2'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '2', 'html': '2'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '2', 'html': '2'},
                        {'sort_key': '3', 'html': '3'}, {'sort_key': '3', 'html': '3'},
                        {'sort_key': 24.0, 'html': 24.0}
                    ],
                    [
                        'Fever cases seen/malaria slides made in malaria endemic area',
                        {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': 0.0, 'html': 0.0}
                    ],
                    [
                        'Acting as DOTS provider', {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': 0.0, 'html': 0.0}],
                    [
                        'Holding or attending village/VHSNC meeting', {'sort_key': '1', 'html': '1'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '0', 'html': '0'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '3', 'html': '3'},
                        {'sort_key': '0', 'html': '0'}, {'sort_key': '3', 'html': '3'},
                        {'sort_key': 11.0, 'html': 11.0}
                    ],
                    [
                        'Successful referral of the IUD, female sterilization or male sterilization cases and/or '
                        'providing OCPs/Condoms',
                        {'sort_key': '5', 'html': '5'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '4', 'html': '4'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '5', 'html': '5'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': '3', 'html': '3'},
                        {'sort_key': '4', 'html': '4'}, {'sort_key': 37.0, 'html': 37.0}
                    ],
                    [
                        '<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                        {'sort_key': 25.925925925925927, 'html': '4/18 (25%)'},
                        {'sort_key': 24.444444444444443, 'html': '3/15 (24%)'},
                        {'sort_key': 25.0, 'html': '4/16 (25%)'},
                        {'sort_key': 24.444444444444443, 'html': '3/15 (24%)'},
                        {'sort_key': 24.444444444444443, 'html': '3/15 (24%)'},
                        {'sort_key': 25.49019607843137, 'html': '4/17 (25%)'},
                        {'sort_key': 19.607843137254903, 'html': '3/17 (19%)'},
                        {'sort_key': 23.809523809523814, 'html': '3/14 (23%)'},
                        {'sort_key': 24.444444444444443, 'html': '3/15 (24%)'},
                        {'sort_key': 21, 'html': '30/142 (21%)'}
                    ],
                    [
                        '<b>Total number of ASHAs who did not report/not known</b>',
                        {'sort_key': '13', 'html': '13'},
                        {'sort_key': '11', 'html': '11'}, {'sort_key': '11', 'html': '11'},
                        {'sort_key': '11', 'html': '11'}, {'sort_key': '11', 'html': '11'},
                        {'sort_key': '12', 'html': '12'}, {'sort_key': '13', 'html': '13'},
                        {'sort_key': '11', 'html': '11'}, {'sort_key': '11', 'html': '11'},
                        {'sort_key': 104.0, 'html': 104.0}
                    ],
                    [
                        '<b>Total Number of ASHAs under each Facilitator</b>', {'sort_key': 18, 'html': 18},
                        {'sort_key': 15, 'html': 15}, {'sort_key': 16, 'html': 16},
                        {'sort_key': 15, 'html': 15}, {'sort_key': 15, 'html': 15},
                        {'sort_key': 17, 'html': 17}, {'sort_key': 17, 'html': 17},
                        {'sort_key': 14, 'html': 14}, {'sort_key': 15, 'html': 15},
                        {'sort_key': 142, 'html': 142}
                    ]
                ], 142
            )
        )

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
        self.assertEqual(
            rows,
            (
                [
                    [
                        'Newborn visits within first day of birth in case of home deliveries',
                        {'sort_key': '1.4%', 'html': '1.4%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '1.6%', 'html': '1.6%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '0.0%', 'html': '0.0%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '3.2%', 'html': '3.2%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '2.1%', 'html': '2.1%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '3.0%', 'html': '3.0%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '3.2%', 'html': '3.2%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '4.7%', 'html': '4.7%'}, {'sort_key': 'D', 'html': 'D'}
                    ],
                    [
                        'Set of home visits for newborn care as specified in the HBNC guidelines<br/>(six visits'
                        ' in case of Institutional delivery and seven in case of a home delivery)',
                        {'sort_key': '18.3%', 'html': '18.3%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '16.3%', 'html': '16.3%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '14.1%', 'html': '14.1%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '18.5%', 'html': '18.5%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '16.4%', 'html': '16.4%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '20.1%', 'html': '20.1%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '17.5%', 'html': '17.5%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '17.1%', 'html': '17.1%'}, {'sort_key': 'D', 'html': 'D'}
                    ],
                    [
                        'Attending VHNDs/Promoting immunization', {'sort_key': '26.8%', 'html': '26.8%'},
                        {'sort_key': 'C', 'html': 'C'}, {'sort_key': '22.5%', 'html': '22.5%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '20.2%', 'html': '20.2%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '26.6%', 'html': '26.6%'},
                        {'sort_key': 'C', 'html': 'C'}, {'sort_key': '25.4%', 'html': '25.4%'},
                        {'sort_key': 'C', 'html': 'C'}, {'sort_key': '27.6%', 'html': '27.6%'},
                        {'sort_key': 'C', 'html': 'C'}, {'sort_key': '25.4%', 'html': '25.4%'},
                        {'sort_key': 'C', 'html': 'C'}, {'sort_key': '24.8%', 'html': '24.8%'},
                        {'sort_key': 'D', 'html': 'D'}
                    ],
                    [
                        'Supporting institutional delivery', {'sort_key': '20.4%', 'html': '20.4%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '20.9%', 'html': '20.9%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '18.2%', 'html': '18.2%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '18.5%', 'html': '18.5%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '20.6%', 'html': '20.6%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '21.6%', 'html': '21.6%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '18.3%', 'html': '18.3%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '16.3%', 'html': '16.3%'},
                        {'sort_key': 'D', 'html': 'D'}
                    ],
                    [
                        'Management of childhood illness - especially diarrhea and pneumonia',
                        {'sort_key': '21.1%', 'html': '21.1%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '15.5%', 'html': '15.5%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '20.2%', 'html': '20.2%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '16.9%', 'html': '16.9%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '14.3%', 'html': '14.3%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '10.4%', 'html': '10.4%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '21.4%', 'html': '21.4%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '18.6%', 'html': '18.6%'}, {'sort_key': 'D', 'html': 'D'}
                    ],
                    [
                        'Household visits with nutrition counseling', {'sort_key': '16.9%', 'html': '16.9%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '7.0%', 'html': '7.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '9.1%', 'html': '9.1%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '0.0%', 'html': '0.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '7.9%', 'html': '7.9%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '0.7%', 'html': '0.7%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '0.0%', 'html': '0.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '12.4%', 'html': '12.4%'},
                        {'sort_key': 'D', 'html': 'D'}
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
                        'Acting as DOTS provider', {'sort_key': '0.0%', 'html': '0.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '5.4%', 'html': '5.4%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '4.0%', 'html': '4.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '4.0%', 'html': '4.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '3.7%', 'html': '3.7%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '2.2%', 'html': '2.2%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '0.0%', 'html': '0.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '6.2%', 'html': '6.2%'},
                        {'sort_key': 'D', 'html': 'D'}
                    ],
                    [
                        'Holding or attending village/VHSNC meeting', {'sort_key': '7.7%', 'html': '7.7%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '1.6%', 'html': '1.6%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '5.1%', 'html': '5.1%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '7.3%', 'html': '7.3%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '0.0%', 'html': '0.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '6.7%', 'html': '6.7%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '4.0%', 'html': '4.0%'},
                        {'sort_key': 'D', 'html': 'D'}, {'sort_key': '10.9%', 'html': '10.9%'},
                        {'sort_key': 'D', 'html': 'D'}
                    ],
                    [
                        'Successful referral of the IUD, female sterilization or male sterilization cases and/or '
                        'providing OCPs/Condoms',
                        {'sort_key': '26.1%', 'html': '26.1%'}, {'sort_key': 'C', 'html': 'C'},
                        {'sort_key': '23.3%', 'html': '23.3%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '24.2%', 'html': '24.2%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '24.2%', 'html': '24.2%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '21.7%', 'html': '21.7%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '25.4%', 'html': '25.4%'}, {'sort_key': 'C', 'html': 'C'},
                        {'sort_key': '23.8%', 'html': '23.8%'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': '24.0%', 'html': '24.0%'}, {'sort_key': 'D', 'html': 'D'}
                    ],
                    [
                        '<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                        {'sort_key': 21, 'html': '30/142 (21%)'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': 18, 'html': '24/129 (18%)'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': 18, 'html': '18/100 (18%)'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': 20, 'html': '26/124 (20%)'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': 19, 'html': '37/189 (19%)'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': 23, 'html': '31/134 (23%)'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': 21, 'html': '27/126 (21%)'}, {'sort_key': 'D', 'html': 'D'},
                        {'sort_key': 21, 'html': '28/129 (21%)'}, {'sort_key': 'D', 'html': 'D'}
                    ]
                ], 0)
        )
