from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.models import AggAwcDailyView
from custom.icds_reports.utils import percent_increase, get_value


def get_system_usage_data(yesterday, config):
    yesterday_date = datetime(*yesterday)
    two_days_ago = (yesterday_date - relativedelta(days=1)).date()

    def get_data_for(date, filters):
        return AggAwcDailyView.objects.filter(
            date=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            awcs=Sum('awc_count'),
            daily_attendance=Sum('daily_attendance_open'),
            num_forms=Sum('usage_num_forms'),
            num_home_visits=Sum('usage_num_home_visit'),
            num_gmp=Sum('usage_num_gmp'),
            num_thr=Sum('usage_num_thr')
        )

    yesterday_data = get_data_for(yesterday_date, config)
    two_days_ago_data = get_data_for(two_days_ago, config)

    return {
        'records': [
            [
                {
                    'label': _('Average number of household registration forms submitted yesterday'),
                    'help_text': _('Average number of household registration forms submitted by AWWs yesterday.'),
                    'percent': percent_increase('num_forms', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'num_forms'),
                    'all': get_value(yesterday_data, 'awcs'),
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('Average number of Home Visit forms submitted yesterday'),
                    'help_text': _(
                        ("Average number of home visit forms submitted yesterday. Home visit forms are "
                         "Birth Preparedness, Delivery, Post Natal Care, Exclusive breastfeeding and "
                         "Complementary feeding")
                    ),
                    'percent': percent_increase('num_home_visits', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'num_home_visits'),
                    'all': get_value(yesterday_data, 'awcs'),
                    'format': 'number'
                },
                {
                    'label': _('Average number of Growth Monitoring forms submitted yesterday'),
                    'help_text': _('Average number of growth monitoring forms (GMP) submitted yesterday'),
                    'percent': percent_increase('num_gmp', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'num_gmp'),
                    'all': get_value(yesterday_data, 'awcs'),
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('Average number of Take Home Ration forms submitted yesterday'),
                    'help_text': _('Average number of Take Home Rations (THR) forms submitted yesterday'),
                    'percent': percent_increase('num_thr', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'num_thr'),
                    'all': get_value(yesterday_data, 'awcs'),
                    'format': 'number'
                }
            ]
        ]
    }
