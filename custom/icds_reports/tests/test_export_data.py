from __future__ import absolute_import

from __future__ import unicode_literals
from datetime import date
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.test.testcases import TestCase
import mock

from custom.icds_reports.sqldata import ChildrenExport, PregnantWomenExport, ExportableMixin, DemographicsExport, \
    SystemUsageExport, AWCInfrastructureExport, BeneficiaryExport


class TestExportData(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestExportData, cls).setUpClass()
        cls.india_now_mock = mock.patch.object(
            ExportableMixin,
            'india_now',
            new_callable=mock.PropertyMock(return_value='16:21:11 15 November 2017')
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
        self.assertEqual(len(data), 11)

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
                "1.42 %",
                317,
                "2.60 %",
                "23.21 %",
                "74.20 %",
                "0.00 %",
                "38.46 %",
                '53.85 %',
                "38.46 %",
                "46.15 %",
                "15.38 %",
                "66.67 %",
                "14.77%",
                "37.50 %",
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
                '1.42 %',
                317,
                '2.60 %',
                '23.21 %',
                '74.20 %',
                '0.00 %',
                '38.46 %',
                '53.85 %',
                '38.46 %',
                '46.15 %',
                '15.38 %',
                "66.67 %",
                '14.77%',
                '37.50 %',
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
                "1.42 %",
                317,
                "2.60 %",
                "23.21 %",
                "74.20 %",
                "0.00 %",
                "38.46 %",
                '53.85 %',
                "38.46 %",
                "46.15 %",
                "15.38 %",
                "66.67 %",
                "14.77%",
                "37.50 %",
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
                "1.42 %",
                317,
                "2.60 %",
                "23.21 %",
                "74.20 %",
                "0.00 %",
                "38.46 %",
                '53.85 %',
                "38.46 %",
                "46.15 %",
                "15.38 %",
                "66.67 %",
                "14.77%",
                "37.50 %",
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
                "1.42 %",
                317,
                "2.60 %",
                "23.21 %",
                "74.20 %",
                "0.00 %",
                "38.46 %",
                '53.85 %',
                "38.46 %",
                "46.15 %",
                "15.38 %",
                "66.67 %",
                "14.77%",
                "37.50 %",
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
                "3.04 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "3.45 %",
                "13.79 %",
                '62.07 %',
                "36.67 %",
                "20.00 %",
                "43.33 %",
                "0.00 %",
                "7.19%",
                "42.86 %",
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
                "3.04 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "3.45 %",
                "13.79 %",
                '62.07 %',
                "36.67 %",
                "20.00 %",
                "43.33 %",
                "0.00 %",
                "7.19%",
                "42.86 %",
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
                "3.04 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "3.45 %",
                "13.79 %",
                '62.07 %',
                "36.67 %",
                "20.00 %",
                "43.33 %",
                "0.00 %",
                "7.19%",
                "42.86 %",
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
                "3.04 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "3.45 %",
                "13.79 %",
                '62.07 %',
                "36.67 %",
                "20.00 %",
                "43.33 %",
                "0.00 %",
                "7.19%",
                "42.86 %",
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
                "3.04 %",
                307,
                "2.46 %",
                "18.85 %",
                "78.69 %",
                "3.45 %",
                "13.79 %",
                '62.07 %',
                "36.67 %",
                "20.00 %",
                "43.33 %",
                "0.00 %",
                "7.19%",
                "42.86 %",
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
            [
                [
                    "Pregnant Women",
                    [
                        [
                            "State",
                            "Number of lactating women",
                            "Number of pregnant women",
                            "Number of postnatal women",
                            "Percentage Anemia",
                            "Percentage Tetanus Completed",
                            "Percent women had at least 1 ANC visit by delivery",
                            "Percent women had at least 2 ANC visit by delivery",
                            "Percent women had at least 3 ANC visit by delivery",
                            "Percent women had at least 4 ANC visit by delivery",
                            "Percentage of women resting during pregnancy",
                            "Percentage of women eating extra meal during pregnancy",
                            "Percentage of trimester 3 women counselled on immediate breastfeeding"
                        ],
                        [
                            "st1",
                            171,
                            120,
                            38,
                            "22.50%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "89.17 %",
                            "90.00 %",
                            "60.32 %"
                        ],
                        [
                            "st1",
                            171,
                            120,
                            38,
                            "22.50%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "89.17 %",
                            "90.00 %",
                            "60.32 %"
                        ],
                        [
                            "st1",
                            171,
                            120,
                            38,
                            "22.50%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "89.17 %",
                            "90.00 %",
                            "60.32 %"
                        ],
                        [
                            "st1",
                            171,
                            120,
                            38,
                            "22.50%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "89.17 %",
                            "90.00 %",
                            "60.32 %"
                        ],
                        [
                            "st1",
                            171,
                            120,
                            38,
                            "22.50%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "89.17 %",
                            "90.00 %",
                            "60.32 %"
                        ],
                        [
                            "st2",
                            154,
                            139,
                            34,
                            "22.30%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "87.05 %",
                            "86.33 %",
                            "57.97 %"
                        ],
                        [
                            "st2",
                            154,
                            139,
                            34,
                            "22.30%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "87.05 %",
                            "86.33 %",
                            "57.97 %"
                        ],
                        [
                            "st2",
                            154,
                            139,
                            34,
                            "22.30%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "87.05 %",
                            "86.33 %",
                            "57.97 %"
                        ],
                        [
                            "st2",
                            154,
                            139,
                            34,
                            "22.30%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "87.05 %",
                            "86.33 %",
                            "57.97 %"
                        ],
                        [
                            "st2",
                            154,
                            139,
                            34,
                            "22.30%",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "0.00 %",
                            "87.05 %",
                            "86.33 %",
                            "57.97 %"
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

    def test_demographics_export(self):
        self.assertListEqual(
            DemographicsExport(
                config={
                    'domain': 'icds-cas'
                }
            ).get_excel_data('b1'),
            [
                [
                    "Demographics",
                    [
                        [
                            "State",
                            "Number of households",
                            "Total number of beneficiaries (under 6 years old and women between"
                            " 11 and 49 years old, alive and seeking services) who have an aadhaar ID",
                            "Total number of beneficiaries (under 6 years old and women between "
                            "11 and 49 years old, alive and seeking services)",
                            "Percent Aadhaar-seeded beneficaries",
                            "Number of pregnant women",
                            "Number of pregnant women enrolled for services",
                            "Number of lactating women",
                            "Number of lactating women enrolled for services",
                            "Number of children 0-6 years old",
                            "Number of children 0-6 years old enrolled for services",
                            "Number of children 0-6 months old enrolled for services",
                            "Number of children 6 months to 3 years old enrolled for services",
                            "Number of children 3 to 6 years old enrolled for services",
                            "Number of adolescent girls 11 to 14 years old",
                            "Number of adolescent girls 15 to 18 years old",
                            "Number of adolescent girls 11 to 14 years old that are enrolled for services",
                            "Number of adolescent girls 15 to 18 years old that are enrolled for services"
                        ],
                        [
                            "st1",
                            7266,
                            365,
                            1493,
                            "24.45 %",
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            "st1",
                            7266,
                            365,
                            1493,
                            "24.45 %",
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            "st1",
                            7266,
                            365,
                            1493,
                            "24.45 %",
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            "st1",
                            7266,
                            365,
                            1493,
                            "24.45 %",
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            "st1",
                            7266,
                            365,
                            1493,
                            "24.45 %",
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            "st2",
                            6662,
                            269,
                            1590,
                            "16.92 %",
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ],
                        [
                            "st2",
                            6662,
                            269,
                            1590,
                            "16.92 %",
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ],
                        [
                            "st2",
                            6662,
                            269,
                            1590,
                            "16.92 %",
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ],
                        [
                            "st2",
                            6662,
                            269,
                            1590,
                            "16.92 %",
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ],
                        [
                            "st2",
                            6662,
                            269,
                            1590,
                            "16.92 %",
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
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

    def test_demographics_export_flags_being_passed(self):
        self.assertListEqual(
            DemographicsExport(
                config={
                    'domain': 'icds-cas'
                },
                beta=True
            ).get_excel_data('st1'),
            [
                [
                    'Demographics',
                    [
                        [
                            'State', 'Number of households',
                            'Total number of beneficiaries (under 6 years old and women between 11 and 49 years '
                            'old, alive and seeking services) who have an aadhaar ID',
                            'Total number of beneficiaries (under 6 years old and women between 11 and 49 years '
                            'old, alive and seeking services)',
                            'Percent Aadhaar-seeded beneficaries', 'Number of pregnant women',
                            'Number of pregnant women enrolled for services', 'Number of lactating women',
                            'Number of lactating women enrolled for services',
                            'Number of children 0-6 years old',
                            'Number of children 0-6 years old enrolled for services',
                            'Number of children 0-6 months old enrolled for services',
                            'Number of children 6 months to 3 years old enrolled for services',
                            'Number of children 3 to 6 years old enrolled for services',
                            'Number of adolescent girls 11 to 14 years old',
                            'Number of adolescent girls 15 to 18 years old',
                            'Number of adolescent girls 11 to 14 years old that are enrolled for services',
                            'Number of adolescent girls 15 to 18 years old that are enrolled for services'
                        ],
                        [
                            'st1',
                            7266,
                            365,
                            1493,
                            '24.45 %',
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            'st1',
                            7266,
                            365,
                            1493,
                            '24.45 %',
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            'st1',
                            7266,
                            365,
                            1493,
                            '24.45 %',
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            'st1',
                            7266,
                            365,
                            1493,
                            '24.45 %',
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            'st1',
                            7266,
                            365,
                            1493,
                            '24.45 %',
                            120,
                            120,
                            171,
                            171,
                            1227,
                            1227,
                            56,
                            244,
                            927,
                            36,
                            12,
                            36,
                            12
                        ],
                        [
                            'st2',
                            6662,
                            269,
                            1590,
                            '16.92 %',
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ],
                        [
                            'st2',
                            6662,
                            269,
                            1590,
                            '16.92 %',
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ],
                        [
                            'st2',
                            6662,
                            269,
                            1590,
                            '16.92 %',
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ],
                        [
                            'st2',
                            6662,
                            269,
                            1590,
                            '16.92 %',
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ],
                        [
                            'st2',
                            6662,
                            269,
                            1590,
                            '16.92 %',
                            139,
                            139,
                            154,
                            154,
                            1322,
                            1322,
                            52,
                            301,
                            969,
                            36,
                            20,
                            36,
                            20
                        ]
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
                        ]
                    ]
                ]
            ]
        )

    def test_system_usage_export(self):
        self.assertListEqual(
            SystemUsageExport(
                config={
                    'domain': 'icds-cas'
                }
            ).get_excel_data('b1'),
            [
                [
                    "System Usage",
                    [
                        [
                            "State",
                            "Number of days AWC was open in the given month",
                            "Number of launched AWCs (ever submitted at least one HH reg form)",
                            "Number of household registration forms",
                            "Number of add pregnancy forms",
                            "Number of birth preparedness forms",
                            "Number of delivery forms",
                            "Number of PNC forms",
                            "Number of exclusive breastfeeding forms",
                            "Number of complementary feeding forms",
                            "Number of growth monitoring forms",
                            "Number of take home rations forms",
                            "Number of due list forms"
                        ],
                        [
                            "st1",
                            38,
                            16,
                            85,
                            4,
                            4,
                            1,
                            0,
                            5,
                            12,
                            14,
                            47,
                            5
                        ],
                        [
                            "st1",
                            38,
                            16,
                            85,
                            4,
                            4,
                            1,
                            0,
                            5,
                            12,
                            14,
                            47,
                            5
                        ],
                        [
                            "st1",
                            38,
                            16,
                            85,
                            4,
                            4,
                            1,
                            0,
                            5,
                            12,
                            14,
                            47,
                            5
                        ],
                        [
                            "st1",
                            38,
                            16,
                            85,
                            4,
                            4,
                            1,
                            0,
                            5,
                            12,
                            14,
                            47,
                            5
                        ],
                        [
                            "st1",
                            38,
                            16,
                            85,
                            4,
                            4,
                            1,
                            0,
                            5,
                            12,
                            14,
                            47,
                            5
                        ],
                        [
                            "st2",
                            34,
                            22,
                            79,
                            4,
                            4,
                            2,
                            2,
                            5,
                            4,
                            20,
                            65,
                            17
                        ],
                        [
                            "st2",
                            34,
                            22,
                            79,
                            4,
                            4,
                            2,
                            2,
                            5,
                            4,
                            20,
                            65,
                            17
                        ],
                        [
                            "st2",
                            34,
                            22,
                            79,
                            4,
                            4,
                            2,
                            2,
                            5,
                            4,
                            20,
                            65,
                            17
                        ],
                        [
                            "st2",
                            34,
                            22,
                            79,
                            4,
                            4,
                            2,
                            2,
                            5,
                            4,
                            20,
                            65,
                            17
                        ],
                        [
                            "st2",
                            34,
                            22,
                            79,
                            4,
                            4,
                            2,
                            2,
                            5,
                            4,
                            20,
                            65,
                            17
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
                            "Name 1814",
                            "2017-01-28",
                            "4 months ",
                            "M",
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
