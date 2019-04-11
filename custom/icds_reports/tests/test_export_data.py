from __future__ import absolute_import

from __future__ import unicode_literals
from datetime import date, datetime
import json
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED
from django.core.serializers.json import DjangoJSONEncoder
from django.test.testcases import TestCase
import mock

from custom.icds_reports.sqldata.exports.awc_infrastructure import AWCInfrastructureExport
from custom.icds_reports.sqldata.exports.beneficiary import BeneficiaryExport
from custom.icds_reports.sqldata.exports.children import ChildrenExport
from custom.icds_reports.sqldata.exports.demographics import DemographicsExport
from custom.icds_reports.sqldata.exports.lady_supervisor import LadySupervisorExport
from custom.icds_reports.sqldata.exports.pregnant_women import PregnantWomenExport
from custom.icds_reports.sqldata.exports.system_usage import SystemUsageExport
from custom.icds_reports.reports.incentive import IncentiveReport

class TestExportData(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestExportData, cls).setUpClass()
        cls.india_now_mock = mock.patch(
            'custom.icds_reports.utils.mixins.india_now',
            new=mock.Mock(return_value='16:21:11 15 November 2017')
        )
        cls.india_now_mock.start()

    @classmethod
    def tearDownClass(cls):
        cls.india_now_mock.stop()
        super(TestExportData, cls).tearDownClass()

    def test_children_export(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][0]
        self.assertEqual(data, "Children")

    def test_children_export_info(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[1]
        self.assertListEqual(
            data,
            [
                "Export Info",
                [
                    [
                        "Generated at",
                        "16:21:11 15 November 2017"
                    ],
                    [
                        "Block",
                        "b1"
                    ]
                ]
            ]
        )

    def test_children_export_data_length(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1]
        self.assertEqual(len(data), 36)

    def test_children_export_headers(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][0]
        self.assertListEqual(
            data,
            [
                "State",
                "Weighing efficiency (in month)",
                "Height measurement efficiency (in month)",
                "Total number of unweighed children (0-5 Years)",
                "Percentage of severely underweight children",
                "Percentage of moderately underweight children",
                "Percentage of normal weight-for-age children",
                "Percentage of children with severe wasting",
                "Percentage of children with moderate wasting",
                "Percentage of children with normal weight-for-height",
                "Percentage of children with severe stunting",
                "Percentage of children with moderate stunting",
                "Percentage of children with normal height-for-age",
                'Percent of newborns with low birth weight',
                "Percentage of children with completed 1 year immunizations",
                "Percentage of children breastfed at birth",
                "Percentage of children exclusively breastfeeding",
                "Percentage of children initiated complementary feeding (in the past 30 days)",
                "Percentage of children initiated appropriate complementary feeding",
                "Percentage of children receiving complementary feeding with adequate diet diversity",
                "Percentage of children receiving complementary feeding with adequate diet quanity",
                "Percentage of children receiving complementary feeding with appropriate "
                "handwashing before feeding"
            ]
        )

    def test_children_export_child_one(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][1]
        self.assertListEqual(
            data,
            [
                "st1",
                "67.39 %",
                "1.40 %",
                317,
                "2.60 %",
                "23.21 %",
                "74.20 %",
                '7.69 %',
                "38.46 %",
                "53.85 %",
                "38.46 %",
                "46.15 %",
                "15.38 %",
                '50.00 %',
                '14.46%',
                "20.00 %",
                "50.00 %",
                "65.62 %",
                "53.52 %",
                "34.51 %",
                "39.44 %",
                "47.89 %"
            ]
        )

    def test_children_export_child_two(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][2]
        self.assertListEqual(
            data,
            [
                'st1',
                '67.39 %',
                '1.40 %',
                317,
                '2.60 %',
                '23.21 %',
                '74.20 %',
                '7.69 %',
                '38.46 %',
                '53.85 %',
                '38.46 %',
                '46.15 %',
                '15.38 %',
                "50.00 %",
                '14.46%',
                '20.00 %',
                '50.00 %',
                '65.62 %',
                '53.52 %',
                '34.51 %',
                '39.44 %',
                '47.89 %'
            ]
        )

    def test_children_export_child_three(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][3]
        self.assertListEqual(
            data,
            [
                "st1",
                "67.39 %",
                "1.40 %",
                317,
                "2.60 %",
                "23.21 %",
                "74.20 %",
                "7.69 %",
                "38.46 %",
                '53.85 %',
                "38.46 %",
                "46.15 %",
                "15.38 %",
                "50.00 %",
                "14.46%",
                "20.00 %",
                "50.00 %",
                "65.62 %",
                "53.52 %",
                "34.51 %",
                "39.44 %",
                "47.89 %"
            ]
        )

    def test_children_export_child_four(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][4]
        self.assertListEqual(
            data,
            [
                "st1",
                "67.39 %",
                "1.40 %",
                317,
                "2.60 %",
                "23.21 %",
                "74.20 %",
                "7.69 %",
                "38.46 %",
                "53.85 %",
                '38.46 %',
                "46.15 %",
                "15.38 %",
                "50.00 %",
                "14.46%",
                "20.00 %",
                "50.00 %",
                "65.62 %",
                "53.52 %",
                "34.51 %",
                "39.44 %",
                "47.89 %"
            ]
        )

    def test_children_export_child_five(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][5]
        self.assertListEqual(
            data,
            [
                "st1",
                "67.39 %",
                "1.40 %",
                317,
                "2.60 %",
                "23.21 %",
                "74.20 %",
                "7.69 %",
                "38.46 %",
                "53.85 %",
                '38.46 %',
                "46.15 %",
                "15.38 %",
                "50.00 %",
                "14.46%",
                "20.00 %",
                "50.00 %",
                "65.62 %",
                "53.52 %",
                "34.51 %",
                "39.44 %",
                "47.89 %"
            ]
        )

    def test_children_export_child_six(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][6]
        self.assertListEqual(
            data,
            [
                "st2",
                "70.45 %",
                "2.99 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "4.35 %",
                "17.39 %",
                '78.26 %',
                "34.38 %",
                "18.75 %",
                "46.88 %",
                "0.00 %",
                "7.07%",
                "50.00 %",
                "25.00 %",
                "60.00 %",
                "50.81 %",
                "47.03 %",
                "33.51 %",
                "47.57 %"
            ]
        )

    def test_children_export_child_seven(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][7]
        self.assertListEqual(
            data,
            [
                "st2",
                "70.45 %",
                "2.99 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "4.35 %",
                "17.39 %",
                '78.26 %',
                "34.38 %",
                "18.75 %",
                "46.88 %",
                "0.00 %",
                "7.07%",
                "50.00 %",
                "25.00 %",
                "60.00 %",
                "50.81 %",
                "47.03 %",
                "33.51 %",
                "47.57 %"
            ]
        )

    def test_children_export_child_eight(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][8]
        self.assertListEqual(
            data,
            [
                "st2",
                "70.45 %",
                "2.99 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "4.35 %",
                "17.39 %",
                '78.26 %',
                "34.38 %",
                "18.75 %",
                "46.88 %",
                "0.00 %",
                "7.07%",
                "50.00 %",
                "25.00 %",
                "60.00 %",
                "50.81 %",
                "47.03 %",
                "33.51 %",
                "47.57 %"
            ]
        )

    def test_children_export_child_nine(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][9]
        self.assertListEqual(
            data,
            [
                "st2",
                "70.45 %",
                "2.99 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "4.35 %",
                "17.39 %",
                '78.26 %',
                "34.38 %",
                "18.75 %",
                "46.88 %",
                "0.00 %",
                "7.07%",
                "50.00 %",
                "25.00 %",
                "60.00 %",
                "50.81 %",
                "47.03 %",
                "33.51 %",
                "47.57 %"
            ]
        )

    def test_children_export_child_ten(self):
        data = ChildrenExport(
            config={
                'domain': 'icds-cas'
            },
        ).get_excel_data('b1')[0][1][10]
        self.assertListEqual(
            data,
            [
                "st2",
                "70.45 %",
                "2.99 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "4.35 %",
                "17.39 %",
                '78.26 %',
                "34.38 %",
                "18.75 %",
                "46.88 %",
                "0.00 %",
                "7.07%",
                "50.00 %",
                "25.00 %",
                "60.00 %",
                "50.81 %",
                "47.03 %",
                "33.51 %",
                "47.57 %"
            ]
        )

    def test_pregnant_women_export(self):
        self.assertListEqual(
            PregnantWomenExport(
                config={
                    'domain': 'icds-cas'
                }
            ).get_excel_data('b1'),
            [['Pregnant Women', [
                [
                    'State', 'Number of lactating women', 'Number of pregnant women',
                    'Number of postnatal women', 'Percentage Anemia', 'Percentage Tetanus Completed',
                    'Percent women had at least 1 ANC visit by delivery',
                    'Percent women had at least 2 ANC visit by delivery',
                    'Percent women had at least 3 ANC visit by delivery',
                    'Percent women had at least 4 ANC visit by delivery',
                    'Percentage of women resting during pregnancy',
                    'Percentage of women eating extra meal during pregnancy',
                    'Percentage of trimester 3 women counselled on immediate breastfeeding'
                ],
                ['st1', 171, 120, 31, '22.50%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.00 %', '75.83 %', '60.32 %'],
                ['st1', 171, 120, 31, '22.50%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.00 %', '75.83 %', '60.32 %'],
                ['st1', 171, 120, 31, '22.50%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.00 %', '75.83 %', '60.32 %'],
                ['st1', 171, 120, 31, '22.50%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.00 %', '75.83 %', '60.32 %'],
                ['st1', 171, 120, 31, '22.50%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.00 %', '75.83 %', '60.32 %'],
                ['st2', 154, 139, 30, '22.30%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.54 %', '74.82 %', '57.97 %'],
                ['st2', 154, 139, 30, '22.30%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.54 %', '74.82 %', '57.97 %'],
                ['st2', 154, 139, 30, '22.30%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.54 %', '74.82 %', '57.97 %'],
                ['st2', 154, 139, 30, '22.30%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.54 %', '74.82 %', '57.97 %'],
                ['st2', 154, 139, 30, '22.30%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '75.54 %', '74.82 %', '57.97 %'],
                ['st3', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st3', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st3', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st3', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st3', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st4', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st4', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st4', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st4', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st4', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st5', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st5', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st5', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st5', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st5', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st6', 0, 0, 0, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st6', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st6', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st6', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st6', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st7', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st7', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st7', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st7', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %'],
                ['st7', 2, 0, 1, '0.00%', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %', '0.00 %']
                ]],
                [
                    'Export Info',
                    [
                        ['Generated at', '16:21:11 15 November 2017'],
                        ['Block', 'b1']
                    ]
                ]
            ]
        )

    def test_demographics_export(self):
        self.assertListEqual(
            DemographicsExport(
                config={
                    'domain': 'icds-cas'
                },
            ).get_excel_data('st1'),
            [[
                'Demographics',
                [[
                    'State', 'Number of households',
                    'Total number of beneficiaries (Children under 6 years old, pregnant women and lactating women, alive and seeking services) who have an Aadhaar ID',
                    'Total number of beneficiaries (Children under 6 years old, pregnant women and lactating women, alive and seeking services)',
                    'Percent Aadhaar-seeded beneficaries', 'Number of pregnant women',
                    'Number of pregnant women enrolled for services', 'Number of lactating women',
                    'Number of lactating women enrolled for services', 'Number of children 0-6 years old',
                    'Number of children 0-6 years old enrolled for services',
                    'Number of children 0-6 months old enrolled for services',
                    'Number of children 6 months to 3 years old enrolled for services',
                    'Number of children 3 to 6 years old enrolled for services',
                    'Number of adolescent girls 11 to 14 years old',
                    'Number of adolescent girls 15 to 18 years old',
                    'Number of adolescent girls 11 to 14 years old that are enrolled for services',
                    'Number of adolescent girls 15 to 18 years old that are enrolled for services'
                ],
                ['st1', 7266, 369, 1518, '24.31 %', 120, 120, 171, 171, 1227, 1227, 56, 244, 927, 36, 12, 36, 12],
                ['st1', 7266, 369, 1518, '24.31 %', 120, 120, 171, 171, 1227, 1227, 56, 244, 927, 36, 12, 36, 12],
                ['st1', 7266, 369, 1518, '24.31 %', 120, 120, 171, 171, 1227, 1227, 56, 244, 927, 36, 12, 36, 12],
                ['st1', 7266, 369, 1518, '24.31 %', 120, 120, 171, 171, 1227, 1227, 56, 244, 927, 36, 12, 36, 12],
                ['st1', 7266, 369, 1518, '24.31 %', 120, 120, 171, 171, 1227, 1227, 56, 244, 927, 36, 12, 36, 12],
                ['st2', 6662, 275, 1615, '17.03 %', 139, 139, 154, 154, 1322, 1322, 52, 301, 969, 36, 20, 36, 20],
                ['st2', 6662, 275, 1615, '17.03 %', 139, 139, 154, 154, 1322, 1322, 52, 301, 969, 36, 20, 36, 20],
                ['st2', 6662, 275, 1615, '17.03 %', 139, 139, 154, 154, 1322, 1322, 52, 301, 969, 36, 20, 36, 20],
                ['st2', 6662, 275, 1615, '17.03 %', 139, 139, 154, 154, 1322, 1322, 52, 301, 969, 36, 20, 36, 20],
                ['st2', 6662, 275, 1615, '17.03 %', 139, 139, 154, 154, 1322, 1322, 52, 301, 969, 36, 20, 36, 20],
                ['st3', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st3', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st3', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st3', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st3', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st4', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st4', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st4', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st4', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st4', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st5', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st5', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st5', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st5', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st5', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st6', 0, 0, 0, '0.00 %', 0, 0, 0, 0, 0, 0, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st6', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st6', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st6', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st6', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0],
                ['st7', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 1, 0, 0, 0, 0],
                ['st7', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 1, 0, 0, 0, 0],
                ['st7', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 1, 0, 0, 0, 0],
                ['st7', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 1, 0, 0, 0, 0],
                ['st7', 0, 0, 3, '0.00 %', 0, 0, 2, 2, 1, 1, 'Data Not Entered', 'Data Not Entered', 1, 0, 0, 0, 0]
                ]],
                [
                    'Export Info',
                    [
                        ['Generated at', '16:21:11 15 November 2017'],
                        ['State', 'st1']
                    ]
                ]
            ]
        )

    def test_system_usage_export(self):
        self.assertListEqual(
            SystemUsageExport(
                config={
                    'domain': 'icds-cas',
                    'month': datetime(2017, 5, 1)
                }
            ).get_excel_data('b1'),
            [
                ['System Usage', [
                    [
                        'State',
                        'Number of days AWC was open in the given month',
                        'Number of launched AWCs (ever submitted at least one HH reg form)',
                        'Number of household registration forms', 'Number of add pregnancy forms',
                        'Number of birth preparedness forms', 'Number of delivery forms',
                        'Number of PNC forms', 'Number of exclusive breastfeeding forms',
                        'Number of complementary feeding forms', 'Number of growth monitoring forms',
                        'Number of take home rations forms', 'Number of due list forms'
                    ],
                    ['st1', 'Not Applicable', 9, 0, 1, 4, 1, 0, 5, 12, 3, 46, 5],
                    ['st1', 'Not Applicable', 9, 0, 1, 4, 1, 0, 5, 12, 3, 46, 5],
                    ['st1', 'Not Applicable', 9, 0, 1, 4, 1, 0, 5, 12, 3, 46, 5],
                    ['st1', 'Not Applicable', 9, 0, 1, 4, 1, 0, 5, 12, 3, 46, 5],
                    ['st1', 'Not Applicable', 9, 0, 1, 4, 1, 0, 5, 12, 3, 46, 5],
                    ['st2', 'Not Applicable', 11, 0, 4, 4, 1, 1, 4, 4, 20, 65, 17],
                    ['st2', 'Not Applicable', 11, 0, 4, 4, 1, 1, 4, 4, 20, 65, 17],
                    ['st2', 'Not Applicable', 11, 0, 4, 4, 1, 1, 4, 4, 20, 65, 17],
                    ['st2', 'Not Applicable', 11, 0, 4, 4, 1, 1, 4, 4, 20, 65, 17],
                    ['st2', 'Not Applicable', 11, 0, 4, 4, 1, 1, 4, 4, 20, 65, 17],
                    ['st3', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st3', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st3', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st3', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st3', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st4', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st4', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st4', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st4', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st4', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st5', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st5', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st5', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st5', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st5', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st6', 'Data Not Entered', 'Data Not Entered', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st6', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st6', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st6', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st6', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st7', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st7', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st7', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st7', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    ['st7', 'Data Not Entered', 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                ]],
                ['Export Info', [
                    ['Generated at', '16:21:11 15 November 2017'],
                    ['Block', 'b1'],
                    ['Month', 'May'],
                    ['Year', 2017]
                ]]
            ]
        )

    def test_system_usage_export_for_awc_level(self):
        self.assertListEqual(
            SystemUsageExport(
                config={
                    'domain': 'icds-cas',
                    'block_id': 'b1',
                    'aggregation_level': 5,
                    'month': datetime(2017, 5, 1)
                },
                loc_level=5,
            ).get_excel_data('b1', system_usage_num_launched_awcs_formatting_at_awc_level=True),
            [
                ['System Usage', [
                    [
                        'State',
                        'District',
                        'Block',
                        'Supervisor',
                        'AWC',
                        'AWW Phone Number',
                        'Number of days AWC was open in the given month',
                        'Number of launched AWCs (ever submitted at least one HH reg form)',
                        'Number of household registration forms', 'Number of add pregnancy forms',
                        'Number of birth preparedness forms', 'Number of delivery forms',
                        'Number of PNC forms', 'Number of exclusive breastfeeding forms',
                        'Number of complementary feeding forms', 'Number of growth monitoring forms',
                        'Number of take home rations forms', 'Number of due list forms'
                    ],
                    [
                        'st1', 'd1', 'b1', 's1', 'a1', '+91555555',
                        18, 'Not Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's1', 'a17', 'Data Not Entered',
                        11, 'Not Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's1', 'a25', 'Data Not Entered',
                        13, 'Not Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's1', 'a33', 'Data Not Entered',
                        12, 'Not Launched', 0, 0, 0, 1, 0, 0, 0, 0, 0, 1
                    ],
                    [
                        'st1', 'd1', 'b1', 's1', 'a41', 'Data Not Entered',
                        16, 'Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 2
                    ],
                    [
                        'st1', 'd1', 'b1', 's1', 'a49', 'Data Not Entered',
                        14, 'Launched', 0, 0, 0, 0, 0, 0, 1, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's1', 'a9', 'Data Not Entered',
                        18, 'Not Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's2', 'a10', 'Data Not Entered',
                        8, 'Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's2', 'a18', 'Data Not Entered',
                        17, 'Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's2', 'a2', 'Data Not Entered',
                        10, 'Not Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's2', 'a26', 'Data Not Entered',
                        12, 'Not Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's2', 'a34', 'Data Not Entered',
                        4, 'Not Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's2', 'a42', 'Data Not Entered',
                        7, 'Not Launched', 0, 0, 1, 0, 0, 0, 1, 0, 0, 0
                    ],
                    [
                        'st1', 'd1', 'b1', 's2', 'a50', 'Data Not Entered',
                        19, 'Not Launched', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    ]
                ]],
                ['Export Info', [
                    ['Generated at', '16:21:11 15 November 2017'],
                    ['Block', 'b1'],
                    ['Grouped By', 'AWC'],
                    ['Month', 'May'],
                    ['Year', 2017]
                ]],
            ]
        )

    def test_awc_infrastructure_export(self):
        self.assertListEqual(
            AWCInfrastructureExport(
                config={
                    'domain': 'icds-cas'
                }
            ).get_excel_data('b1'),
            [
                [
                    "AWC Infrastructure",
                    [
                        [
                            "State",
                            "Percentage AWCs reported clean drinking water",
                            "Percentage AWCs reported functional toilet",
                            "Percentage AWCs reported medicine kit",
                            "Percentage AWCs reported weighing scale: infants",
                            "Percentage AWCs reported weighing scale: mother and child"
                        ],
                        [
                            "st1",
                            "100.00 %",
                            "50.00 %",
                            "61.54 %",
                            "76.92 %",
                            "26.92 %"
                        ],
                        [
                            "st1",
                            "100.00 %",
                            "50.00 %",
                            "61.54 %",
                            "76.92 %",
                            "26.92 %"
                        ],
                        [
                            "st1",
                            "100.00 %",
                            "50.00 %",
                            "61.54 %",
                            "76.92 %",
                            "26.92 %"
                        ],
                        [
                            "st1",
                            "100.00 %",
                            "50.00 %",
                            "61.54 %",
                            "76.92 %",
                            "26.92 %"
                        ],
                        [
                            "st1",
                            "100.00 %",
                            "50.00 %",
                            "61.54 %",
                            "76.92 %",
                            "26.92 %"
                        ],
                        [
                            "st2",
                            "94.44 %",
                            "55.56 %",
                            "83.33 %",
                            "77.78 %",
                            "27.78 %"
                        ],
                        [
                            "st2",
                            "94.44 %",
                            "55.56 %",
                            "83.33 %",
                            "77.78 %",
                            "27.78 %"
                        ],
                        [
                            "st2",
                            "94.44 %",
                            "55.56 %",
                            "83.33 %",
                            "77.78 %",
                            "27.78 %"
                        ],
                        [
                            "st2",
                            "94.44 %",
                            "55.56 %",
                            "83.33 %",
                            "77.78 %",
                            "27.78 %"
                        ],
                        [
                            "st2",
                            "94.44 %",
                            "55.56 %",
                            "83.33 %",
                            "77.78 %",
                            "27.78 %"
                        ],
                        [
                            'st3',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st3',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st3',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st3',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st3',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st4',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st4',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st4',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        ['st4',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st4',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st5',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st5',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st5',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st5',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st5',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st6',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st6',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st6',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st6',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st6',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st7',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st7',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st7',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st7',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ],
                        [
                            'st7',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered',
                            'Data Not Entered'
                        ]
                    ]
                ],
                [
                    "Export Info",
                    [
                        [
                            "Generated at",
                            "16:21:11 15 November 2017"
                        ],
                        [
                            "Block",
                            "b1"
                        ]
                    ]
                ]
            ]
        )

    def test_beneficiary_export(self):
        self.assertJSONEqual(
            json.dumps(
                BeneficiaryExport(
                    config={
                        'domain': 'icds-cas',
                        'month': date(2017, 5, 1),
                        'awc_id': 'a7'
                    },
                    loc_level=5
                ).get_excel_data('a7'),
                cls=DjangoJSONEncoder
            ),
            json.dumps([
                [
                    "Child Beneficiary",
                    [
                        [
                            "AWC Name",
                            "AWC Site Code",
                            "Supervisor Name",
                            "Block Name",
                            "AWW Phone Number",
                            "Mother Phone Number",
                            "Child Name",
                            "Date of Birth",
                            "Current Age (as of 2017-05-01)",
                            "Sex ",
                            "1 Year Immunizations Complete",
                            "Month for data shown",
                            "Weight Recorded (in Month)",
                            "Height Recorded (in Month)",
                            "Weight-for-Age Status (in Month)",
                            "Weight-for-Height Status (in Month)",
                            "Height-for-Age status (in Month)",
                            "Days attended PSE (as of 2017-05-01)"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 1783",
                            "2013-06-06",
                            "3 years 11 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "11.80",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            23
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 1788",
                            "2012-12-03",
                            "4 years 5 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "12.10",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            19
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 1790",
                            "2012-12-15",
                            "4 years 5 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "13.70",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            20
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 1795",
                            "2014-01-20",
                            "3 years 4 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "11.30",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            17
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 1797",
                            "2012-05-12",
                            "5 years ",
                            "M",
                            "No",
                            "2017-05-01",
                            "15.70",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            23
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 1832",
                            "2015-09-14",
                            "1 year 8 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "10.60",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 1876",
                            "2016-01-11",
                            "1 year 4 months ",
                            "M",
                            "Yes",
                            "2017-05-01",
                            "8.80",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2027",
                            "2016-12-15",
                            "5 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2054",
                            "2016-05-26",
                            "1 year ",
                            "M",
                            "No",
                            "2017-05-01",
                            "8.60",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2056",
                            "2014-11-29",
                            "2 years 6 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "11.40",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2060",
                            "2015-10-10",
                            "1 year 7 months ",
                            "M",
                            "Yes",
                            "2017-05-01",
                            "8.80",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2073",
                            "2015-08-10",
                            "1 year 9 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "9.50",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2094",
                            "2014-12-04",
                            "2 years 5 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "10.50",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2117",
                            "2015-11-18",
                            "1 year 6 months ",
                            "M",
                            "Yes",
                            "2017-05-01",
                            "9.80",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2134",
                            "2015-12-12",
                            "1 year 5 months ",
                            "M",
                            "Yes",
                            "2017-05-01",
                            "7.90",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2141",
                            "2015-03-05",
                            "2 years 2 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "10.00",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2171",
                            "2016-08-27",
                            "9 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "7.50",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2173",
                            "2015-05-24",
                            "2 years ",
                            "M",
                            "No",
                            "2017-05-01",
                            "9.40",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2182",
                            "2014-12-12",
                            "2 years 5 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "11.50",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2188",
                            "2014-08-16",
                            "2 years 9 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "11.40",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2192",
                            "2015-10-07",
                            "1 year 7 months ",
                            "F",
                            "Yes",
                            "2017-05-01",
                            "8.00",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2207",
                            "2016-01-21",
                            "1 year 4 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "8.70",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2210",
                            "2015-05-18",
                            "2 years ",
                            "M",
                            "No",
                            "2017-05-01",
                            "9.60",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2241",
                            "2012-10-14",
                            "4 years 7 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "13.00",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            21
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2250",
                            "2014-06-10",
                            "2 years 11 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "11.70",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2254",
                            "2013-01-28",
                            "4 years 4 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "14.00",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            18
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2263",
                            "2016-09-08",
                            "8 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "8.70",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2265",
                            "2014-02-16",
                            "3 years 3 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "11.80",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            18
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2266",
                            "2014-03-13",
                            "3 years 2 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "11.60",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            22
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2267",
                            "2012-12-25",
                            "4 years 5 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "13.60",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            20
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2271",
                            "2013-05-13",
                            "4 years ",
                            "F",
                            "No",
                            "2017-05-01",
                            "12.20",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            24
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2276",
                            "2012-07-22",
                            "4 years 10 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "13.80",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            22
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2330",
                            "2013-06-29",
                            "3 years 11 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "13.50",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            21
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2331",
                            "2013-05-09",
                            "4 years ",
                            "F",
                            "No",
                            "2017-05-01",
                            "12.40",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            19
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2333",
                            "2014-06-05",
                            "2 years 11 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "10.70",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Data Not Entered"
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2335",
                            "2013-10-14",
                            "3 years 7 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "11.90",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            20
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2337",
                            "2013-12-04",
                            "3 years 5 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "12.60",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            26
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2338",
                            "2013-07-03",
                            "3 years 10 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "14.20",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            24
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2339",
                            "2013-11-29",
                            "3 years 6 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "12.90",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            27
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2340",
                            "2013-07-25",
                            "3 years 10 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "13.10",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            17
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2341",
                            "2012-08-07",
                            "4 years 9 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "14.20",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            24
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2342",
                            "2013-09-24",
                            "3 years 8 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "11.00",
                            "Data Not Entered",
                            "Moderately underweight",
                            "Data Not Entered",
                            "Data Not Entered",
                            24
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2344",
                            "2013-03-09",
                            "4 years 2 months ",
                            "M",
                            "No",
                            "2017-05-01",
                            "13.40",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            22
                        ],
                        [
                            "a7",
                            "a7",
                            "s7",
                            "b4",
                            "Data Not Entered",
                            "Data Not Entered",
                            "Name 2346",
                            "2014-01-20",
                            "3 years 4 months ",
                            "F",
                            "No",
                            "2017-05-01",
                            "12.70",
                            "Data Not Entered",
                            "Normal weight for age",
                            "Data Not Entered",
                            "Data Not Entered",
                            16
                        ]
                    ]
                ],
                [
                    "Export Info",
                    [
                        [
                            "Generated at",
                            "16:21:11 15 November 2017"
                        ],
                        [
                            "Awc",
                            "a7"
                        ],
                        [
                            "Month",
                            "May"
                        ],
                        [
                            "Year",
                            2017
                        ]
                    ]
                ]
            ])
        )

    def test_lady_supervisor_export(self):
        data = LadySupervisorExport(
            config={
                'domain': 'icds-cas',
                'aggregation_level': 4,
                'month': date(2017, 5, 1),
                'state_id': 'st1',
            },
            loc_level=1,
        ).get_excel_data('st1')
        expected = [
            [
                'Lady Supervisor',
                [
                    [
                        'State',
                        'District',
                        'Block',
                        'Sector Name',
                        'Name of Lady Supervisor',
                        'Total No. of AWCs visited',
                        'Total No. of Beneficiaries Visited',
                        'Total No. of VHNDs observed'
                    ],
                    [
                        'st1',
                        'd1',
                        'b1',
                        's1',
                        's1',
                        1,
                        2,
                        'Data Not Entered'
                    ],
                    [
                        'st1',
                        'd1',
                        'b1',
                        's2',
                        's2',
                        1,
                        1,
                        2
                    ],
                    [
                        'st1',
                        'd1',
                        'b2',
                        's3',
                        's3',
                        'Data Not Entered',
                        2,
                        'Data Not Entered'
                    ],
                    [
                        'st1',
                        'd1',
                        'b2',
                        's4',
                        's4',
                        'Data Not Entered',
                        'Data Not Entered',
                        1
                    ],
                ]
            ],
            [
                'Export Info',
                [
                    [
                        'Generated at',
                        '16:21:11 15 November 2017'
                    ],
                    [
                        'State',
                        'st1'
                    ],
                    [
                        'Grouped By',
                        'Supervisor'
                    ],
                    [
                        'Month',
                        'May'
                    ],
                    [
                        'Year',
                        2017
                    ]
                ]
            ]
        ]
        self.assertListEqual(
            data,
            expected
        )

    def test_aww_performance_export(self):
        data = IncentiveReport(
            location='b2',
            month=datetime(2017,5,1),
            aggregation_level=3
        ).get_excel_data()

        expected = [
            ['AWW Performance Report',
             [['State', 'District', 'Block', 'Supervisor', 'AWC', 'AWW Name', 'AWW Contact Number',
               'Home Visits Conducted', 'Number of Days AWC was Open', 'Weighing Efficiency',
               'Eligible for Incentive'],
              ['st1', 'd1', 'b2', 's4', 'a12', 'AWC not launched', 'AWC not launched', 'AWC not launched',
               'AWC not launched', 'AWC not launched', 'AWC not launched'],
              ['st1', 'd1', 'b2', 's4', 'a28', 'Data Not Entered', 'Data Not Entered', '0.00%', 5, '0.00%',
               'No'],
              ['st1', 'd1', 'b2', 's4', 'a4', 'AWC not launched', 'AWC not launched', 'AWC not launched',
               'AWC not launched', 'AWC not launched', 'AWC not launched'],
              ['st1', 'd1', 'b2', 's4', 'a36', 'Data Not Entered', 'Data Not Entered', '0.00%', 17, '7.50%',
               'No'],
              ['st1', 'd1', 'b2', 's4', 'a20', 'AWC not launched', 'AWC not launched', 'AWC not launched',
               'AWC not launched', 'AWC not launched', 'AWC not launched'],
              ['st1', 'd1', 'b2', 's4', 'a44', 'AWC not launched', 'AWC not launched', 'AWC not launched',
               'AWC not launched', 'AWC not launched', 'AWC not launched'],
              ['st1', 'd1', 'b2', 's3', 'a27', 'AWC not launched', 'AWC not launched', 'AWC not launched',
               'AWC not launched', 'AWC not launched', 'AWC not launched'],
              ['st1', 'd1', 'b2', 's3', 'a11', 'AWC not launched', 'AWC not launched', 'AWC not launched',
               'AWC not launched', 'AWC not launched', 'AWC not launched'],
              ['st1', 'd1', 'b2', 's3', 'a19', 'Data Not Entered', 'Data Not Entered', '0.00%', 16, '90.00%',
               'No'],
              ['st1', 'd1', 'b2', 's3', 'a3', 'AWC not launched', 'AWC not launched', 'AWC not launched',
               'AWC not launched', 'AWC not launched', 'AWC not launched'],
              ['st1', 'd1', 'b2', 's3', 'a35', 'Data Not Entered', 'Data Not Entered', '0.00%', 12, '100.00%',
               'No'],
              ['st1', 'd1', 'b2', 's3', 'a43', 'Data Not Entered', 'Data Not Entered', '0.00%', 13, '90.48%',
               'No']]],
            ['Export Info',
                          [
                              ['Generated at', india_now()],
                              ['Grouped By', 'AWC'],
                              ['Month', 5],
                              ['Year', 2017],
                              ['Disclaimer',
                               'The information in the report is based on the self-reported '
                               'data entered by the Anganwadi Worker in ICDS-CAS mobile application'
                               ' and is subject to timely data syncs.']
                          ]
             ]
        ]
        self.assertListEqual(
            data,
            expected
        )