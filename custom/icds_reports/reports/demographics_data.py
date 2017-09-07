from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.models import AggAwcDailyView
from custom.icds_reports.utils import percent_increase, percent_diff, get_value, apply_exclude


def get_demographics_data(domain, yesterday, config, show_test=False):
    yesterday_date = datetime(*yesterday)
    two_days_ago = (yesterday_date - relativedelta(days=1)).date()

    def get_data_for(date, filters):
        queryset = AggAwcDailyView.objects.filter(
            date=date, **filters
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
            person_adolescent=Sum('cases_person_adolescent_girls_11_18'),
            person_adolescent_all=Sum('cases_person_adolescent_girls_11_18_all'),
            person_aadhaar=Sum('cases_person_has_aadhaar'),
            all_persons=Sum('cases_person')
        )

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    yesterday_data = get_data_for(yesterday_date, config)
    two_days_ago_data = get_data_for(two_days_ago, config)

    return {
        'records': [
            [
                {
                    'label': _('Registered Households'),
                    'help_text': _('Total number of households registered'),
                    'percent': percent_increase('household', yesterday_data, two_days_ago_data),
                    'color': 'green' if percent_increase(
                        'household',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'household'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day',
                    'redirect': 'registered_household'
                },
                {
                    'label': _('Children (0-6 years)'),
                    'help_text': _('Total number of children registered between the age of 0 - 6 years'),
                    'percent': percent_increase('child_health_all', yesterday_data, two_days_ago_data),
                    'color': 'green' if percent_increase(
                        'child_health_all',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'child_health_all'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day',
                    'redirect': 'enrolled_children'
                }
            ],
            [
                {
                    'label': _('Children (0-6 years) enrolled for ICDS services'),
                    'help_text': _((
                        "Total number of children registered between the age of 0 - 6 years "
                        "and enrolled for ICDS services"
                    )),
                    'percent': percent_increase('child_health', yesterday_data, two_days_ago_data),
                    'color': 'green' if percent_increase(
                        'child_health',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'child_health'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Pregnant Women'),
                    'help_text': _('Total number of pregnant women registered'),
                    'percent': percent_increase('ccs_pregnant_all', yesterday_data, two_days_ago_data),
                    'color': 'green' if percent_increase(
                        'ccs_pregnant_all',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'ccs_pregnant_all'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day',
                    'redirect': 'enrolled_women'
                }
            ], [
                {
                    'label': _('Pregnant Women enrolled for ICDS services'),
                    'help_text': _('Total number of pregnant women registered and enrolled for ICDS services'),
                    'percent': percent_increase('ccs_pregnant', yesterday_data, two_days_ago_data),
                    'color': 'green' if percent_increase(
                        'ccs_pregnant',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'ccs_pregnant'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Lactating Women'),
                    'help_text': _('Total number of lactating women registered'),
                    'percent': percent_increase('css_lactating_all', yesterday_data, two_days_ago_data),
                    'color': 'green' if percent_increase(
                        'css_lactating_all',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'css_lactating_all'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day',
                    'redirect': 'lactating_enrolled_women'
                }
            ], [
                {
                    'label': _('Lactating Women enrolled for ICDS services'),
                    'help_text': _('Total number of lactating women registered and enrolled for ICDS services'),
                    'percent': percent_increase('css_lactating', yesterday_data, two_days_ago_data),
                    'color': 'green' if percent_increase(
                        'css_lactating',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'css_lactating'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Adolescent Girls (11-18 years)'),
                    'help_text': _('Total number of adolescent girls (11 - 18 years) who are registered'),
                    'percent': percent_increase(
                        'person_adolescent_all',
                        yesterday_data,
                        two_days_ago_data
                    ),
                    'color': 'green' if percent_increase(
                        'person_adolescent_all',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'person_adolescent_all'),
                    'all': None,
                    'format': 'number',
                    'redirect': 'adolescent_girls'
                }
            ], [
                {
                    'label': _('Adolescent Girls (11-18 years) enrolled for ICDS services'),
                    'help_text': _((
                        "Total number of adolescent girls (11 - 18 years) "
                        "who are registered and enrolled for ICDS services"
                    )),
                    'percent': percent_increase(
                        'person_adolescent',
                        yesterday_data,
                        two_days_ago_data
                    ),
                    'color': 'green' if percent_increase(
                        'person_adolescent',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'person_adolescent'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Percent Adhaar Seeded Individuals'),
                    'help_text': _((
                        'Percentage of ICDS beneficiaries whose Adhaar identification has been captured'
                    )),
                    'percent': percent_diff(
                        'person_aadhaar',
                        yesterday_data,
                        two_days_ago_data,
                        'all_persons'
                    ),
                    'color': 'green' if percent_increase(
                        'person_aadhaar',
                        yesterday_data,
                        two_days_ago_data) > 0 else 'red',
                    'value': get_value(yesterday_data, 'person_aadhaar'),
                    'all': get_value(yesterday_data, 'all_persons'),
                    'format': 'percent_and_div',
                    'frequency': 'day',
                    'redirect': 'adhaar'
                }
            ]
        ]
    }
