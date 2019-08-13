from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Sum, Max
from django.utils.translation import ugettext as _

from custom.icds_reports.messages import awcs_launched_help_text
from custom.icds_reports.models import AggAwcMonthly, AggAwcDailyView
from custom.icds_reports.utils import get_value, percent_increase, apply_exclude, get_color_with_green_positive


def get_cas_reach_data(domain, now_date, config, show_test=False):
    now_date = datetime(*now_date)

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
            awc_num_open=Sum('awc_num_open') if level <= 5 else Max('awc_num_open'),
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

    current_month_selected = (current_month.year == now_date.year and current_month.month == now_date.month)

    if current_month_selected:
        date = now_date.date()
        daily_yesterday = None
        # keep the record in searched - current - month
        while daily_yesterday is None or (not daily_yesterday and date.day != 1):
            date -= relativedelta(days=1)
            daily_yesterday = get_data_for_daily_usage(date, config)
        daily_two_days_ago = None
        while daily_two_days_ago is None or (not daily_two_days_ago and date.day != 1):
            date -= relativedelta(days=1)
            daily_two_days_ago = get_data_for_daily_usage(date, config)
        daily_attendance_percent = percent_increase('daily_attendance', daily_yesterday, daily_two_days_ago)
        number_of_awc_open_yesterday = {
            'label': _('Number of AWCs Open yesterday'),
            'help_text': _(("Total Number of Angwanwadi Centers that were open yesterday "
                            "by the AWW or the AWW helper")),
            'color': get_color_with_green_positive(daily_attendance_percent),
            'percent': daily_attendance_percent,
            'value': get_value(daily_yesterday, 'daily_attendance'),
            'all': get_value(awc_this_month_data, 'awcs'),
            'format': 'div',
            'frequency': 'day',
            'redirect': 'icds_cas_reach/awc_daily_status',
        }
    else:
        awc_prev_month_data = get_data_for_awc_monthly(previous_month, config)
        monthly_attendance_percent = percent_increase('awc_num_open', awc_this_month_data, awc_prev_month_data)
        number_of_awc_open_yesterday = {
            'help_text': _("Total Number of AWCs open for at least one day in month"),
            'label': _('Number of AWCs open for at least one day in month'),
            'color': get_color_with_green_positive(monthly_attendance_percent),
            'percent': monthly_attendance_percent,
            'value': get_value(awc_this_month_data, 'awc_num_open'),
            'all': get_value(awc_this_month_data, 'awcs'),
            'format': 'div',
            'frequency': 'month',
        }

    return {
        'records': [
            [
                {
                    'label': _('AWCs Launched'),
                    'help_text': awcs_launched_help_text(),
                    'color': None,
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'awcs'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month',
                    'redirect': 'icds_cas_reach/awcs_covered'
                },
                number_of_awc_open_yesterday
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
