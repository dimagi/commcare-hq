from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _


from custom.icds_reports.models import AggAwcMonthly, AggAwcDailyView
from custom.icds_reports.utils import get_value, percent_increase, apply_exclude


def get_cas_reach_data(domain, yesterday, config, show_test=False):
    yesterday_date = datetime(*yesterday)
    two_days_ago = (yesterday_date - relativedelta(days=1)).date()

    def get_data_for_awc_monthly(month, filters):
        queryset = AggAwcMonthly.objects.filter(
            month=month, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            states=Sum('num_launched_states'),
            districts=Sum('num_launched_districts'),
            blocks=Sum('num_launched_blocks'),
            supervisors=Sum('num_launched_supervisors'),
            awcs=Sum('num_launched_awcs'),

        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    def get_data_for_daily_usage(date, filters):
        queryset = AggAwcDailyView.objects.filter(
            date=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            awcs=Sum('num_awcs'),
            daily_attendance=Sum('daily_attendance_open')
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    current_month = datetime(*config['month'])
    previous_month = datetime(*config['prev_month'])
    del config['month']
    del config['prev_month']

    awc_this_month_data = get_data_for_awc_monthly(current_month, config)
    awc_prev_month_data = get_data_for_awc_monthly(previous_month, config)

    daily_yesterday = get_data_for_daily_usage(yesterday_date, config)
    daily_two_days_ago = get_data_for_daily_usage(two_days_ago, config)

    return {
        'records': [
            [
                {
                    'label': _('AWCs covered'),
                    'help_text': _('Total AWCs that have launched ICDS CAS'),
                    'percent': percent_increase('awcs', awc_this_month_data, awc_prev_month_data),
                    'color': 'green' if percent_increase(
                        'awcs',
                        awc_this_month_data,
                        awc_prev_month_data) > 0 else 'red',
                    'value': get_value(awc_this_month_data, 'awcs'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                    'redirect': 'awcs_covered'
                },
                {
                    'label': _('Number of AWCs Open yesterday'),
                    'help_text': _(("Total Number of Angwanwadi Centers that were open yesterday "
                                    "by the AWW or the AWW helper")),
                    'percent': percent_increase('daily_attendance', daily_yesterday, daily_two_days_ago),
                    'value': get_value(daily_yesterday, 'daily_attendance'),
                    'all': get_value(daily_yesterday, 'awcs'),
                    'format': 'div',
                    'frequency': 'day',
                    'redirect': 'awc_daily_status'
                }
            ],
            [
                {
                    'label': _('Sectors covered'),
                    'help_text': _('Total Sectors that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'supervisors'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                    'redirect': 'awcs_covered'
                },
                {
                    'label': _('Blocks covered'),
                    'help_text': _('Total Blocks that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'blocks'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                    'redirect': 'awcs_covered'
                },
            ],
            [

                {
                    'label': _('Districts covered'),
                    'help_text': _('Total Districts that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'districts'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                    'redirect': 'awcs_covered'
                },
                {
                    'label': _('States/UTs covered'),
                    'help_text': _('Total States that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'states'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                    'redirect': 'awcs_covered'
                }
            ]
        ]
    }
