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
                [u'', u'Date when cheklist was filled', u'Total no. of ASHAs functional on each tasks'],
                [1, u'Newborn visits within first day of birth in case of home deliveries', 0], [2,
                                                                                                 u'Set of home visits for newborn care as specified in the HBNC guidelines (six visits in case of Institutional delivery and seven in case of a home delivery)',
                                                                                                 0],
                [3, u'Attending VHNDs/Promoting immunization', 0], [4, u'Supporting institutional delivery', 0],
                [5, u'Management of childhood illness - especially diarrhea and pneumonia', 0],
                [6, u'Household visits with nutrition counseling', 0],
                [7, u'Fever cases seen/malaria slides made in malaria endemic area', 0],
                [8, u'Acting as DOTS provider', 0], [9, u'Holding or attending village/VHSNC meeting', 0], [10,
                                                                                                            u'Successful referral of the IUD, female sterilization or male sterilization cases and/or providing OCPs/Condoms',
                                                                                                            0],
                [u'', u'Total of number of tasks on which ASHA reported being functional', u''],
                [u'', u'Total number of ASHAs who are functional on at least 60% of the tasks', 0],
                [u'', u'Remark', u'']
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
                        u'Newborn visits within first day of birth in case of home deliveries', u'--',
                        {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Set of home visits for newborn care as specified in the HBNC guidelines<br/>(six visits '
                        u'in case of Institutional delivery and seven in case of a home delivery)',
                        u'--', {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Attending VHNDs/Promoting immunization', u'--', {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Supporting institutional delivery', u'--', {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Management of childhood illness - especially diarrhea and pneumonia', u'--',
                        {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Household visits with nutrition counseling', u'--', {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Fever cases seen/malaria slides made in malaria endemic area', u'--',
                        {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Acting as DOTS provider', u'--', {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Holding or attending village/VHSNC meeting', u'--', {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'Successful referral of the IUD, female sterilization or male sterilization cases and/or '
                        u'providing OCPs/Condoms',
                        u'--', {u'sort_key': 17L, u'html': 17L}, u''
                    ],
                    [
                        u'<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                        {u'sort_key': 0.0, u'html': u'0/17 (0%)'}, {u'sort_key': 17L, u'html': 17L}, u''
                    ]
                ], 17L, 0L
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
                    [u'Newborn visits within first day of birth in case of home deliveries',
                     {u'sort_key': 1L, u'html': 1L}, u'--', u'--', {u'sort_key': u'0', u'html': u'0'}
                     ],
                    [
                        u'Set of home visits for newborn care as specified in the HBNC guidelines<br/>(six visits '
                        u'in case of Institutional delivery and seven in case of a home delivery)',
                        {u'sort_key': 8L, u'html': 8L}, u'--', u'--', {u'sort_key': u'3', u'html': u'3'}
                    ],
                    [
                        u'Attending VHNDs/Promoting immunization', {u'sort_key': 12L, u'html': 12L}, u'--', u'--',
                        {u'sort_key': u'4', u'html': u'4'}
                    ],
                    [
                        u'Supporting institutional delivery', {u'sort_key': 12L, u'html': 12L}, u'--', u'--',
                        {u'sort_key': u'4', u'html': u'4'}
                    ],
                    [
                        u'Management of childhood illness - especially diarrhea and pneumonia',
                        {u'sort_key': 9L, u'html': 9L}, u'--', u'--', {u'sort_key': u'3', u'html': u'3'}
                    ],
                    [
                        u'Household visits with nutrition counseling', {u'sort_key': 4L, u'html': 4L}, u'--',
                        u'--',
                        {u'sort_key': u'1', u'html': u'1'}
                    ],
                    [
                        u'Fever cases seen/malaria slides made in malaria endemic area',
                        {u'sort_key': 0L, u'html': 0L},
                        u'--', u'--', {u'sort_key': u'0', u'html': u'0'}
                    ],
                    [
                        u'Acting as DOTS provider', {u'sort_key': 0L, u'html': 0L}, u'--', u'--',
                        {u'sort_key': u'0', u'html': u'0'}
                    ],
                    [
                        u'Holding or attending village/VHSNC meeting', {u'sort_key': 0L, u'html': 0L}, u'--',
                        u'--',
                        {u'sort_key': u'0', u'html': u'0'}
                    ],
                    [
                        u'Successful referral of the IUD, female sterilization or male sterilization cases '
                        u'and/or providing OCPs/Condoms',
                        {u'sort_key': 12L, u'html': 12L}, u'--', u'--', {u'sort_key': u'4', u'html': u'4'}
                    ],
                    [
                        u'<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                        {u'sort_key': 64.70588235294117, u'html': u'11/17 (64%)'},
                        {u'sort_key': 0.0, u'html': u'0/17 (0%)'}, {u'sort_key': 0.0, u'html': u'0/17 (0%)'},
                        {u'sort_key': 21.56862745098039, u'html': u'3/17 (21%)'}
                    ],
                    [
                        u'<b>Total number of ASHAs who did not report/not known</b>',
                        {u'sort_key': 17L, u'html': 17L},
                        {u'sort_key': 17L, u'html': 17L}, {u'sort_key': 4L, u'html': 4L},
                        {u'sort_key': u'13', u'html': u'13'}
                    ]
                ], 17L)
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
                        u'Newborn visits within first day of birth in case of home deliveries',
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'2', u'html': u'2'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': 2.0, u'html': 2.0}
                    ],
                    [
                        u'Set of home visits for newborn care as specified in the HBNC guidelines<br/>(six visits '
                        u'in case of Institutional delivery and seven in case of a home delivery)',
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'2', u'html': u'2'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'2', u'html': u'2'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'2', u'html': u'2'},
                        {u'sort_key': u'2', u'html': u'2'}, {u'sort_key': 26.0, u'html': 26.0}
                    ],
                    [
                        u'Attending VHNDs/Promoting immunization', {u'sort_key': u'5', u'html': u'5'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'5', u'html': u'5'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'5', u'html': u'5'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': 38.0, u'html': 38.0}
                    ],
                    [
                        u'Supporting institutional delivery', {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'1', u'html': u'1'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': 29.0, u'html': 29.0}
                    ],
                    [
                        u'Management of childhood illness - especially diarrhea and pneumonia',
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': u'2', u'html': u'2'}, {u'sort_key': 30.0, u'html': 30.0}
                    ],
                    [
                        u'Household visits with nutrition counseling', {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'2', u'html': u'2'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'2', u'html': u'2'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'2', u'html': u'2'},
                        {u'sort_key': u'3', u'html': u'3'}, {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': 24.0, u'html': 24.0}
                    ],
                    [
                        u'Fever cases seen/malaria slides made in malaria endemic area',
                        {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': 0.0, u'html': 0.0}
                    ],
                    [
                        u'Acting as DOTS provider', {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': 0.0, u'html': 0.0}],
                    [
                        u'Holding or attending village/VHSNC meeting', {u'sort_key': u'1', u'html': u'1'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'0', u'html': u'0'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': u'0', u'html': u'0'}, {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': 11.0, u'html': 11.0}
                    ],
                    [
                        u'Successful referral of the IUD, female sterilization or male sterilization cases and/or '
                        u'providing OCPs/Condoms',
                        {u'sort_key': u'5', u'html': u'5'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'4', u'html': u'4'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'5', u'html': u'5'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': u'3', u'html': u'3'},
                        {u'sort_key': u'4', u'html': u'4'}, {u'sort_key': 37.0, u'html': 37.0}
                    ],
                    [
                        u'<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                        {u'sort_key': 25.925925925925927, u'html': u'4/18 (25%)'},
                        {u'sort_key': 24.444444444444443, u'html': u'3/15 (24%)'},
                        {u'sort_key': 25.0, u'html': u'4/16 (25%)'},
                        {u'sort_key': 24.444444444444443, u'html': u'3/15 (24%)'},
                        {u'sort_key': 24.444444444444443, u'html': u'3/15 (24%)'},
                        {u'sort_key': 25.49019607843137, u'html': u'4/17 (25%)'},
                        {u'sort_key': 19.607843137254903, u'html': u'3/17 (19%)'},
                        {u'sort_key': 23.809523809523814, u'html': u'3/14 (23%)'},
                        {u'sort_key': 24.444444444444443, u'html': u'3/15 (24%)'},
                        {u'sort_key': 21, u'html': u'30/142 (21%)'}
                    ],
                    [
                        u'<b>Total number of ASHAs who did not report/not known</b>',
                        {u'sort_key': u'13', u'html': u'13'},
                        {u'sort_key': u'11', u'html': u'11'}, {u'sort_key': u'11', u'html': u'11'},
                        {u'sort_key': u'11', u'html': u'11'}, {u'sort_key': u'11', u'html': u'11'},
                        {u'sort_key': u'12', u'html': u'12'}, {u'sort_key': u'13', u'html': u'13'},
                        {u'sort_key': u'11', u'html': u'11'}, {u'sort_key': u'11', u'html': u'11'},
                        {u'sort_key': 104.0, u'html': 104.0}
                    ],
                    [
                        u'<b>Total Number of ASHAs under each Facilitator</b>', {u'sort_key': 18L, u'html': 18L},
                        {u'sort_key': 15L, u'html': 15L}, {u'sort_key': 16L, u'html': 16L},
                        {u'sort_key': 15L, u'html': 15L}, {u'sort_key': 15L, u'html': 15L},
                        {u'sort_key': 17L, u'html': 17L}, {u'sort_key': 17L, u'html': 17L},
                        {u'sort_key': 14L, u'html': 14L}, {u'sort_key': 15L, u'html': 15L},
                        {u'sort_key': 142L, u'html': 142L}
                    ]
                ], 142L
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
                        u'Newborn visits within first day of birth in case of home deliveries',
                        {u'sort_key': u'1.4%', u'html': u'1.4%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'1.6%', u'html': u'1.6%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'0.0%', u'html': u'0.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'3.2%', u'html': u'3.2%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'2.1%', u'html': u'2.1%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'3.0%', u'html': u'3.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'3.2%', u'html': u'3.2%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'4.7%', u'html': u'4.7%'}, {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Set of home visits for newborn care as specified in the HBNC guidelines<br/>(six visits'
                        u' in case of Institutional delivery and seven in case of a home delivery)',
                        {u'sort_key': u'18.3%', u'html': u'18.3%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'16.3%', u'html': u'16.3%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'14.1%', u'html': u'14.1%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'18.5%', u'html': u'18.5%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'16.4%', u'html': u'16.4%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'20.1%', u'html': u'20.1%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'17.5%', u'html': u'17.5%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'17.1%', u'html': u'17.1%'}, {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Attending VHNDs/Promoting immunization', {u'sort_key': u'26.8%', u'html': u'26.8%'},
                        {u'sort_key': u'C', u'html': u'C'}, {u'sort_key': u'22.5%', u'html': u'22.5%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'20.2%', u'html': u'20.2%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'26.6%', u'html': u'26.6%'},
                        {u'sort_key': u'C', u'html': u'C'}, {u'sort_key': u'25.4%', u'html': u'25.4%'},
                        {u'sort_key': u'C', u'html': u'C'}, {u'sort_key': u'27.6%', u'html': u'27.6%'},
                        {u'sort_key': u'C', u'html': u'C'}, {u'sort_key': u'25.4%', u'html': u'25.4%'},
                        {u'sort_key': u'C', u'html': u'C'}, {u'sort_key': u'24.8%', u'html': u'24.8%'},
                        {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Supporting institutional delivery', {u'sort_key': u'20.4%', u'html': u'20.4%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'20.9%', u'html': u'20.9%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'18.2%', u'html': u'18.2%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'18.5%', u'html': u'18.5%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'20.6%', u'html': u'20.6%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'21.6%', u'html': u'21.6%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'18.3%', u'html': u'18.3%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'16.3%', u'html': u'16.3%'},
                        {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Management of childhood illness - especially diarrhea and pneumonia',
                        {u'sort_key': u'21.1%', u'html': u'21.1%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'15.5%', u'html': u'15.5%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'20.2%', u'html': u'20.2%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'16.9%', u'html': u'16.9%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'14.3%', u'html': u'14.3%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'10.4%', u'html': u'10.4%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'21.4%', u'html': u'21.4%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'18.6%', u'html': u'18.6%'}, {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Household visits with nutrition counseling', {u'sort_key': u'16.9%', u'html': u'16.9%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'7.0%', u'html': u'7.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'9.1%', u'html': u'9.1%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'0.0%', u'html': u'0.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'7.9%', u'html': u'7.9%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'0.7%', u'html': u'0.7%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'0.0%', u'html': u'0.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'12.4%', u'html': u'12.4%'},
                        {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Fever cases seen/malaria slides made in malaria endemic area',
                        {u'sort_key': u'0.0%', u'html': u'0.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'0.0%', u'html': u'0.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'1.0%', u'html': u'1.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'0.0%', u'html': u'0.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'0.0%', u'html': u'0.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'0.0%', u'html': u'0.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'0.0%', u'html': u'0.0%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'0.0%', u'html': u'0.0%'}, {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Acting as DOTS provider', {u'sort_key': u'0.0%', u'html': u'0.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'5.4%', u'html': u'5.4%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'4.0%', u'html': u'4.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'4.0%', u'html': u'4.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'3.7%', u'html': u'3.7%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'2.2%', u'html': u'2.2%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'0.0%', u'html': u'0.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'6.2%', u'html': u'6.2%'},
                        {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Holding or attending village/VHSNC meeting', {u'sort_key': u'7.7%', u'html': u'7.7%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'1.6%', u'html': u'1.6%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'5.1%', u'html': u'5.1%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'7.3%', u'html': u'7.3%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'0.0%', u'html': u'0.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'6.7%', u'html': u'6.7%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'4.0%', u'html': u'4.0%'},
                        {u'sort_key': u'D', u'html': u'D'}, {u'sort_key': u'10.9%', u'html': u'10.9%'},
                        {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'Successful referral of the IUD, female sterilization or male sterilization cases and/or '
                        u'providing OCPs/Condoms',
                        {u'sort_key': u'26.1%', u'html': u'26.1%'}, {u'sort_key': u'C', u'html': u'C'},
                        {u'sort_key': u'23.3%', u'html': u'23.3%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'24.2%', u'html': u'24.2%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'24.2%', u'html': u'24.2%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'21.7%', u'html': u'21.7%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'25.4%', u'html': u'25.4%'}, {u'sort_key': u'C', u'html': u'C'},
                        {u'sort_key': u'23.8%', u'html': u'23.8%'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': u'24.0%', u'html': u'24.0%'}, {u'sort_key': u'D', u'html': u'D'}
                    ],
                    [
                        u'<b>Total number of ASHAs who are functional on at least 60% of the tasks</b>',
                        {u'sort_key': 21, u'html': u'30/142 (21%)'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': 18, u'html': u'24/129 (18%)'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': 18, u'html': u'18/100 (18%)'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': 20, u'html': u'26/124 (20%)'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': 19, u'html': u'37/189 (19%)'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': 23, u'html': u'31/134 (23%)'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': 21, u'html': u'27/126 (21%)'}, {u'sort_key': u'D', u'html': u'D'},
                        {u'sort_key': 21, u'html': u'28/129 (21%)'}, {u'sort_key': u'D', u'html': u'D'}
                    ]
                ], 0)
        )
