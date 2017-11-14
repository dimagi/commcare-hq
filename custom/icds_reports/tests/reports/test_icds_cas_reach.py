from __future__ import absolute_import
from django.test import TestCase

from custom.icds_reports.reports.cas_reach_data import get_cas_reach_data


class TestICDSCASReach(TestCase):

    def test_data(self):
        self.assertDictEqual(
            get_cas_reach_data(
                'icds-cas',
                (2017, 5, 28),
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            ),
            {
                "records": [
                    [
                        {
                            "redirect": "awcs_covered",
                            "color": "red",
                            "all": 50,
                            "frequency": "month",
                            "format": "div",
                            "help_text": "Total AWCs that have launched ICDS-CAS. "
                                         "AWCs are considered launched if they have submitted"
                                         " at least one Household Registration form. ",
                            "percent": 0.0,
                            "value": 19,
                            "label": "AWCs covered"
                        },
                        {
                            "redirect": "awc_daily_status",
                            "color": "red",
                            "all": 50,
                            "frequency": "day",
                            "format": "div",
                            "help_text": "Total Number of Angwanwadi Centers that"
                                         " were open yesterday by the AWW or the AWW helper",
                            "percent": 0.0,
                            "value": 0,
                            "label": "Number of AWCs Open yesterday"
                        }
                    ],
                    [
                        {
                            "all": None,
                            "format": "number",
                            "percent": None,
                            "value": 8,
                            "label": "Sectors covered",
                            "frequency": "month",
                            "help_text": "Total Sectors that have launched ICDS CAS"
                        },
                        {
                            "all": None,
                            "format": "number",
                            "percent": None,
                            "value": 4,
                            "label": "Blocks covered",
                            "frequency": "month",
                            "help_text": "Total Blocks that have launched ICDS CAS"
                        }
                    ],
                    [
                        {
                            "all": None,
                            "format": "number",
                            "percent": None,
                            "value": 3,
                            "label": "Districts covered",
                            "frequency": "month",
                            "help_text": "Total Districts that have launched ICDS CAS"
                        },
                        {
                            "all": None,
                            "format": "number",
                            "percent": None,
                            "value": 2,
                            "label": "States/UTs covered",
                            "frequency": "month",
                            "help_text": "Total States that have launched ICDS CAS"
                        }
                    ]
                ]
            }
        )
