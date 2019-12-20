from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.const import AADHAR_SEEDED_BENEFICIARIES, CHILDREN_ENROLLED_FOR_ANGANWADI_SERVICES, \
    PREGNANT_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES, LACTATING_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES, \
    ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES, ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES_V2, \
    ADOLESCENT_GIRLS_DATA_THRESHOLD
from custom.icds_reports.messages import percent_aadhaar_seeded_beneficiaries_help_text, \
    percent_children_enrolled_help_text, percent_pregnant_women_enrolled_help_text, \
    percent_lactating_women_enrolled_help_text, percent_adolescent_girls_enrolled_help_text, \
    percent_adolescent_girls_enrolled_help_text_v2
from custom.icds_reports.models import AggAwcDailyView, AggAwcMonthly
from custom.icds_reports.utils import (
    percent_increase, percent_diff, get_value, apply_exclude,
    person_has_aadhaar_column, person_is_beneficiary_column,
    get_color_with_green_positive,
)


def get_adolescent_girls_data(domain, filters, show_test):
    queryset = AggAwcMonthly.objects.filter(
        **filters
    ).values(
            'aggregation_level'
        ).annotate(
        person_adolescent=Sum('cases_person_adolescent_girls_11_14_out_of_school'),
        person_adolescent_all=Sum('cases_person_adolescent_girls_11_14_all_v2'),

        )
    if not show_test:
        queryset = apply_exclude(domain, queryset)

    return queryset

def get_demographics_data(domain, now_date, config, show_test=False, beta=False):
    now_date = datetime(*now_date)
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
            person_adolescent=Sum('cases_person_adolescent_girls_11_14'),
            person_adolescent_all=Sum('cases_person_adolescent_girls_11_14_all'),
            person_aadhaar=Sum(person_has_aadhaar_column(beta)),
            all_persons=Sum(person_is_beneficiary_column(beta))
        )

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    if current_month.month == now_date.month and current_month.year == now_date.year:
        config['date'] = now_date.date()
        data = None
        # keep the record in searched - current - month
        while data is None or (not data and config['date'].day != 1):
            config['date'] -= relativedelta(days=1)
            data = get_data_for(AggAwcDailyView, config)
        prev_data = None
        while prev_data is None or (not prev_data and config['date'].day != 1):
            config['date'] -= relativedelta(days=1)
            prev_data = get_data_for(AggAwcDailyView, config)
        frequency = 'day'
    else:
        config['month'] = current_month
        data = get_data_for(AggAwcMonthly, config)
        config['month'] = previous_month
        prev_data = get_data_for(AggAwcMonthly, config)
        frequency = 'month'

    if beta:
        if 'date' in config:
            del config['date']
        config['month'] = current_month
        ag_data = get_adolescent_girls_data(domain, config, show_test)
        config['month'] = previous_month
        ag_data_prev_data = get_adolescent_girls_data(domain, config, show_test)

    demographics_data = {
        'records': [
            [
                {
                    'label': _('Registered Households'),
                    'help_text': _('Total number of households registered'),
                    'percent': percent_increase('household', data, prev_data),
                    'color': get_color_with_green_positive(percent_increase(
                        'household',
                        data,
                        prev_data)),
                    'value': get_value(data, 'household'),
                    'all': None,
                    'format': 'number',
                    'frequency': frequency,
                    'redirect': 'demographics/registered_household'
                },
                {
                    'label': _(AADHAR_SEEDED_BENEFICIARIES),
                    'help_text': percent_aadhaar_seeded_beneficiaries_help_text(),
                    'percent': percent_diff(
                        'person_aadhaar',
                        data,
                        prev_data,
                        'all_persons'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'person_aadhaar',
                        data,
                        prev_data,
                        'all_persons')),
                    'value': get_value(data, 'person_aadhaar'),
                    'all': get_value(data, 'all_persons'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'demographics/adhaar'
                }
            ],
            [
                {
                    'label': _(CHILDREN_ENROLLED_FOR_ANGANWADI_SERVICES),
                    'help_text': percent_children_enrolled_help_text(),
                    'percent': percent_diff('child_health', data, prev_data, 'child_health_all'),
                    'color': get_color_with_green_positive(percent_diff(
                        'child_health',
                        data,
                        prev_data, 'child_health_all')),
                    'value': get_value(data, 'child_health'),
                    'all': get_value(data, 'child_health_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'demographics/enrolled_children'
                },
                {
                    'label': _(PREGNANT_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES),
                    'help_text': percent_pregnant_women_enrolled_help_text(),
                    'percent': percent_diff('ccs_pregnant', data, prev_data, 'ccs_pregnant_all'),
                    'color': get_color_with_green_positive(percent_diff(
                        'ccs_pregnant',
                        data,
                        prev_data,
                        'ccs_pregnant_all'
                    )),
                    'value': get_value(data, 'ccs_pregnant'),
                    'all': get_value(data, 'ccs_pregnant_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'demographics/enrolled_women'
                }
            ],
            [

                {
                    'label': _(LACTATING_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES),
                    'help_text': percent_lactating_women_enrolled_help_text(),
                    'percent': percent_diff('css_lactating', data, prev_data, 'css_lactating_all'),
                    'color': get_color_with_green_positive(percent_diff(
                        'css_lactating',
                        data,
                        prev_data,
                        'css_lactating_all'
                    )),
                    'value': get_value(data, 'css_lactating'),
                    'all': get_value(data, 'css_lactating_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                    'redirect': 'demographics/lactating_enrolled_women'
                }

            ]
        ]
    }

    if (not beta) or current_month.date() >= ADOLESCENT_GIRLS_DATA_THRESHOLD:
        adolescent_girls = {
            'label': _(ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES_V2 if beta else
                       ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES),
            'help_text': percent_adolescent_girls_enrolled_help_text_v2() if beta else percent_adolescent_girls_enrolled_help_text(),
            'percent': percent_diff(
                'person_adolescent',
                ag_data if beta else data,
                ag_data_prev_data if beta else prev_data,
                'person_adolescent_all'
            ),
            'color': get_color_with_green_positive(percent_diff(
                'person_adolescent',
                ag_data if beta else data,
                ag_data_prev_data if beta else prev_data,
                'person_adolescent_all'
            )),
            'value': get_value(ag_data if beta else data, 'person_adolescent'),
            'all': get_value(ag_data if beta else data, 'person_adolescent_all'),
            'format': 'percent_and_div',
            'frequency': frequency,
            'redirect': 'demographics/adolescent_girls'
        }
        demographics_data['records'][-1].append(adolescent_girls)

    return demographics_data
