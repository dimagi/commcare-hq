from django.test import TestCase

from custom.icds_reports.messages import awcs_launched_help_text, ls_launched_help_text
from custom.icds_reports.reports.cas_reach_data import get_cas_reach_data


class TestICDSCASReach(TestCase):
    def test_data(self):
        self.assertDictEqual(
            get_cas_reach_data(
                'icds-cas',
                (2017, 6, 1),
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                },
                show_test=False,
            ),
            {
                "records": [
                    [
                        {
                            'redirect': 'icds_cas_reach/awcs_covered',
                            'all': None,
                            'color': None,
                            'format': 'number',
                            'percent': None,
                            'value': 22,
                            'label': 'AWCs Launched',
                            'frequency': 'month',
                            'help_text': awcs_launched_help_text()
                        },
                        {
                            'all': 22,
                            'format': 'number_and_percent',
                            'color': 'green',
                            'percent': 127.27272727272728,
                            'value': 50,
                            'label': 'Number of AWCs open for at least one day in month',
                            'frequency': 'month',
                            'help_text': 'Total Number of AWCs open for at least one day in month'
                        }
                    ],
                    [
                        {
                            'all': None,
                            'color': None,
                            'format': 'number',
                            'frequency': 'month',
                            'help_text': ls_launched_help_text(),
                            'label': 'LSs Launched',
                            'percent': None,
                            'redirect': 'icds_cas_reach/ls_launched',
                            'value': 6
                        },
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 9,
                            'label': 'Sectors covered',
                            'frequency': 'month',
                            'help_text': 'Total Sectors that have launched ICDS CAS'
                        }
                    ],
                    [
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 5,
                            'label': 'Blocks covered',
                            'frequency': 'month',
                            'help_text': 'Total Blocks that have launched ICDS CAS'
                        },
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 4,
                            'label': 'Districts covered',
                            'frequency': 'month',
                            'help_text': 'Total Districts that have launched ICDS CAS'
                        }
                    ],
                    [
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 3,
                            'label': 'States/UTs covered',
                            'frequency': 'month',
                            'help_text': 'Total States that have launched ICDS CAS'
                        }
                    ]
                ]
            }
        )

    def test_data_daily(self):
        self.assertDictEqual(
            get_cas_reach_data(
                'icds-cas',
                (2017, 5, 29),
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                },
                show_test=False,
            ),
            {
                "records": [
                    [
                        {
                            'redirect': 'icds_cas_reach/awcs_covered',
                            'all': None,
                            'color': None,
                            'format': 'number',
                            'percent': None,
                            'value': 22,
                            'label': 'AWCs Launched',
                            'frequency': 'month',
                            'help_text': awcs_launched_help_text()
                        },
                        {
                            'redirect': 'icds_cas_reach/awc_daily_status',
                            'all': 22,
                            'format': 'number_and_percent',
                            'color': 'red',
                            'percent': -97.05882352941177,
                            'value': 1,
                            'label': 'Number of AWCs Open yesterday',
                            'frequency': 'day',
                            'help_text': 'Total Number of Angwanwadi Centers that '
                                         'were open yesterday by the AWW or the AWW helper'
                        }
                    ],
                    [
                        {
                            'all': None,
                            'color': None,
                            'format': 'number',
                            'frequency': 'month',
                            'help_text': ls_launched_help_text(),
                            'label': 'LSs Launched',
                            'percent': None,
                            'redirect': 'icds_cas_reach/ls_launched',
                            'value': 6
                        },
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 9,
                            'label': 'Sectors covered',
                            'frequency': 'month',
                            'help_text': 'Total Sectors that have launched ICDS CAS'
                        }
                    ],
                    [
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 5,
                            'label': 'Blocks covered',
                            'frequency': 'month',
                            'help_text': 'Total Blocks that have launched ICDS CAS'
                        },
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 4,
                            'label': 'Districts covered',
                            'frequency': 'month',
                            'help_text': 'Total Districts that have launched ICDS CAS'
                        }
                    ],
                    [
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 3,
                            'label': 'States/UTs covered',
                            'frequency': 'month',
                            'help_text': 'Total States that have launched ICDS CAS'
                        }
                    ]
                ]
            }
        )

    def test_data_if_aggregation_script_fail(self):
        self.assertDictEqual(
            get_cas_reach_data(
                'icds-cas',
                (2017, 5, 30),
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                },
                show_test=False,
            ),
            {
                "records": [
                    [
                        {
                            'redirect': 'icds_cas_reach/awcs_covered',
                            'all': None,
                            'color': None,
                            'format': 'number',
                            'percent': None,
                            'value': 22,
                            'label': 'AWCs Launched',
                            'frequency': 'month',
                            'help_text': awcs_launched_help_text()
                        },
                        {
                            'redirect': 'icds_cas_reach/awc_daily_status',
                            'all': 22,
                            'format': 'number_and_percent',
                            'color': 'red',
                            'percent': -97.05882352941177,
                            'value': 1,
                            'label': 'Number of AWCs Open yesterday',
                            'frequency': 'day',
                            'help_text': 'Total Number of Angwanwadi Centers that '
                                         'were open yesterday by the AWW or the AWW helper'
                        }
                    ],
                    [
                        {
                            'all': None,
                            'color': None,
                            'format': 'number',
                            'frequency': 'month',
                            'help_text': ls_launched_help_text(),
                            'label': 'LSs Launched',
                            'percent': None,
                            'redirect': 'icds_cas_reach/ls_launched',
                            'value': 6
                        },
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 9,
                            'label': 'Sectors covered',
                            'frequency': 'month',
                            'help_text': 'Total Sectors that have launched ICDS CAS'
                        }
                    ], 
                    [
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 5,
                            'label': 'Blocks covered',
                            'frequency': 'month',
                            'help_text': 'Total Blocks that have launched ICDS CAS'
                        },
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 4,
                            'label': 'Districts covered',
                            'frequency': 'month',
                            'help_text': 'Total Districts that have launched ICDS CAS'
                        }
                    ],
                    [
                        {
                            'all': None,
                            'format': 'number',
                            'percent': None,
                            'value': 3,
                            'label': 'States/UTs covered',
                            'frequency': 'month',
                            'help_text': 'Total States that have launched ICDS CAS'
                        }
                    ]
                ]
            }
        )
