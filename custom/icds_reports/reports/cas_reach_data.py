from __future__ import absolute_import
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Sum, Max
from django.utils.translation import ugettext as _

from corehq.util.quickcache import quickcache
from custom.icds_reports.models import AggAwcMonthly, AggAwcDailyView
from custom.icds_reports.utils import get_value, percent_increase, apply_exclude


@quickcache(['domain', 'now_date', 'config', 'show_test'], timeout=30 * 60)
def get_cas_reach_data(domain, now_date, config, show_test=False):
    now_date = datetime(*now_date)
    yesterday_date = (now_date - relativedelta(days=1)).date()
    two_days_ago = (now_date - relativedelta(days=2)).date()

    def get_data_for_awc_monthly(month, filters):
        level = filters['aggregation_level']
        queryset = AggAwcMonthly.objects.filter(
            month=month, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            states=Sum('num_launched_states') if level <= 1 else Max('num_launched_states'),
            districts=Sum('num_launched_districts') if level <= 2 else Max('num_launched_districts'),
            blocks=Sum('num_launched_blocks') if level <= 3 else Max('num_launched_blocks'),
            supervisors=Sum('num_launched_supervisors') if level <= 4 else Max('num_launched_supervisors'),
            awcs=Sum('num_launched_awcs') if level <= 5 else Max('num_launched_awcs'),
            all_awcs=Sum('num_awcs') if level <= 5 else Max('num_awcs')
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
    if not daily_yesterday:
        daily_yesterday = daily_two_days_ago
        daily_two_days_ago = get_data_for_daily_usage((now_date - relativedelta(days=3)).date(), config)

    daily_attendance_percent = percent_increase('daily_attendance', daily_yesterday, daily_two_days_ago)

    return {
        'records': [
            [
                {
                    'label': _('AWCs Launched'),
                    'help_text': _('Total AWCs that have launched ICDS-CAS. '
                                   'AWCs are considered launched after submitting at least '
                                   'one Household Registration form. '),
                    'percent': percent_increase('awcs', awc_this_month_data, awc_prev_month_data),
                    'color': 'green' if percent_increase(
                        'awcs',
                        awc_this_month_data,
                        awc_prev_month_data) > 0 else 'red',
                    'value': get_value(awc_this_month_data, 'awcs'),
                    'all': get_value(awc_this_month_data, 'all_awcs'),
                    'format': 'div',
                    'frequency': 'month',
                    'redirect': 'awcs_covered'
                },
                {
                    'label': _('Number of AWCs Open yesterday'),
                    'help_text': _(("Total Number of Angwanwadi Centers that were open yesterday "
                                    "by the AWW or the AWW helper")),
                    'color': 'green' if daily_attendance_percent > 0 else 'red',
                    'percent': daily_attendance_percent,
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
                },
                {
                    'label': _('Blocks covered'),
                    'help_text': _('Total Blocks that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'blocks'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
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
                },
                {
                    'label': _('States/UTs covered'),
                    'help_text': _('Total States that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'states'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                }
            ]
        ]
    }
