from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from django.utils.translation import ugettext as _

from corehq.util.quickcache import quickcache
from custom.icds_reports.messages import lady_supervisor_number_of_vhnds_observed_help_text, \
    lady_supervisor_number_of_beneficiaries_visited_help_text, lady_supervisor_number_of_awcs_visited_help_text
from custom.icds_reports.models.views import AggLsMonthly
from custom.icds_reports.utils import get_value, apply_exclude


@quickcache(['domain', 'config', 'show_test'], timeout=30 * 60)
def get_lady_supervisor_data(domain, config, show_test=False):

    def get_data(date, filters):
        queryset = AggLsMonthly.objects.filter(
            month=date, **filters
        ).values(
            "aggregation_level",
            "awc_visits",
            "vhnd_observed",
            "beneficiary_vists",
            "num_launched_awcs",
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    current_month = datetime(*config['month'])
    del config['month']

    data = get_data(current_month, config)

    return {
        'records': [
            [
                {
                    'label': _('Number of AWCs visited'),
                    'help_text': lady_supervisor_number_of_awcs_visited_help_text(),
                    'percent': None,
                    'value': get_value(data, 'awc_visits'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                },
                {
                    'label': _('Number of Beneficiaries Visited'),
                    'help_text': lady_supervisor_number_of_beneficiaries_visited_help_text(),
                    'percent': None,
                    'value': get_value(data, 'beneficiary_vists'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                }
            ],
            [
                {
                    'label': _('Number of VHSNDs observed'),
                    'help_text': lady_supervisor_number_of_vhnds_observed_help_text(),
                    'percent': None,
                    'value': get_value(data, 'vhnd_observed'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                }
            ]
        ]
    }
