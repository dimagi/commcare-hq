from __future__ import absolute_import
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.util.quickcache import quickcache
from custom.icds_reports.models import AggAwcDailyView, AggAwcMonthly
from custom.icds_reports.utils import percent_increase, percent_diff, get_value, apply_exclude


@quickcache(['domain', 'yesterday', 'config', 'show_test'], timeout=30 * 60)
def get_demographics_data(domain, yesterday, config, show_test=False):
    yesterday_date = datetime(*yesterday)
    two_days_ago = (yesterday_date - relativedelta(days=1)).date()
    current_month = datetime(*config['month'])
    previous_month = datetime(*config['prev_month'])
    del config['month']
    del config['prev_month']

    def get_data_for(query_class, filters):
        queryset = query_class.objects.filter(
            **filters
        ).values(
            'aggregation_level'
        ).annotate(
            household=Sum('cases_household'),
            child_health=Sum('cases_child_health'),
            child_health_all=Sum('cases_child_health_all'),
            ccs_pregnant=Sum('cases_ccs_pregnant'),
            ccs_pregnant_all=Sum('cases_ccs_pregnant_all'),
            css_lactating=Sum('cases_ccs_lactating'),
            css_lactating_all=Sum('cases_ccs_lactating_all'),
            person_adolescent=(
                Sum('cases_person_adolescent_girls_11_14') +
                Sum('cases_person_adolescent_girls_15_18')
            ),
            person_adolescent_all=(
                Sum('cases_person_adolescent_girls_11_14_all') +
                Sum('cases_person_adolescent_girls_15_18_all')
            ),
            person_aadhaar=Sum('cases_person_has_aadhaar'),
            all_persons=Sum('cases_person_beneficiary')
        )

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    now = datetime.utcnow()
    if current_month.month == now.month and current_month.year == now.year:
        config['date'] = yesterday_date
        data = get_data_for(AggAwcDailyView, config)
        config['date'] = two_days_ago
        prev_data = get_data_for(AggAwcDailyView, config)
        frequency = 'day'
    else:
        config['month'] = current_month
        data = get_data_for(AggAwcMonthly, config)
        config['month'] = previous_month
        prev_data = get_data_for(AggAwcMonthly, config)
        frequency = 'month'

    return {
        'records': [
            [
                {
                    'label': _('Registered Households'),
                    'help_text': _('Total number of households registered'),
                    'percent': percent_increase('household', data, prev_data),
                    'color': 'green' if percent_increase(
                        'household',
                        data,
                        prev_data) > 0 else 'red',
                    'value': get_value(data, 'household'),
                    'all': None,
                    'format': 'number',
                    'frequency': frequency,
                    'redirect': 'registered_household'
                },
                {
                    'label': _('Percent Aadhaar-seeded Beneficiaries'),
                    'help_text': _((
                        'Percentage of ICDS beneficiaries whose Aadhaar identification has been captured'
                    )),
                    'percent': percent_diff(
                        'person_aadhaar',
                        data,
                        prev_data,
                        'all_persons'
                    ),
                    'color': 'green' if percent_increase(
                        'person_aadhaar',
                        data,
                        prev_data) > 0 else 'red',
                    'value': get_value(data, 'person_aadhaar'),
                    'all': get_value(data, 'all_persons'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'adhaar'
                }
            ],
            [
                {
                    'label': _('Percent children (0-6 years) enrolled for ICDS services'),
                    'help_text': _('Percentage of children registered between '
                                   '0-6 years old who are enrolled for ICDS services'),
                    'percent': percent_diff('child_health', data, prev_data, 'child_health_all'),
                    'color': 'green' if percent_diff(
                        'child_health_all',
                        data,
                        prev_data, 'child_health_all') > 0 else 'red',
                    'value': get_value(data, 'child_health'),
                    'all': get_value(data, 'child_health_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'enrolled_children'
                },
                {
                    'label': _('Percent pregnant women enrolled for ICDS services'),
                    'help_text': _('Percentage of pregnant women registered who are enrolled for ICDS services'),
                    'percent': percent_diff('ccs_pregnant', data, prev_data, 'ccs_pregnant_all'),
                    'color': 'green' if percent_diff(
                        'ccs_pregnant',
                        data,
                        prev_data,
                        'ccs_pregnant_all'
                    ) > 0 else 'red',
                    'value': get_value(data, 'ccs_pregnant'),
                    'all': get_value(data, 'ccs_pregnant_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'enrolled_women'
                }
            ],
            [

                {
                    'label': _('Percent lactating women enrolled for ICDS services'),
                    'help_text': _('Percentage of lactating women registered who are enrolled for ICDS services'),
                    'percent': percent_diff('css_lactating', data, prev_data, 'css_lactating_all'),
                    'color': 'green' if percent_diff(
                        'css_lactating',
                        data,
                        prev_data,
                        'css_lactating_all'
                    ) > 0 else 'red',
                    'value': get_value(data, 'css_lactating'),
                    'all': get_value(data, 'css_lactating_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'lactating_enrolled_women'
                },
                {
                    'label': _('Percent adolescent girls (11-18 years) enrolled for ICDS services'),
                    'help_text': _((
                        "Percentage of adolescent girls registered between 11-18 years"
                        " old who are enrolled for ICDS services"
                    )),
                    'percent': percent_diff(
                        'person_adolescent',
                        data,
                        prev_data,
                        'person_adolescent_all'
                    ),
                    'color': 'green' if percent_diff(
                        'person_adolescent',
                        data,
                        prev_data,
                        'person_adolescent_all'
                    ) > 0 else 'red',
                    'value': get_value(data, 'person_adolescent'),
                    'all': get_value(data, 'person_adolescent_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'adolescent_girls'
                }
            ]
        ]
    }
