from __future__ import absolute_import
from datetime import datetime

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.util.quickcache import quickcache
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import apply_exclude, percent_diff, get_value


@quickcache(['domain', 'config', 'show_test'], timeout=30 * 60)
def get_awc_infrastructure_data(domain, config, show_test=False):
    def get_data_for(month, filters):
        queryset = AggAwcMonthly.objects.filter(
            month=month, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            clean_water=Sum('infra_clean_water'),
            functional_toilet=Sum('infra_functional_toilet'),
            medicine_kits=Sum('infra_medicine_kits'),
            infant_scale=Sum('infra_infant_weighing_scale'),
            adult_scale=Sum('infra_adult_weighing_scale'),
            awcs=Sum('num_awcs')
        )

        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    current_month = datetime(*config['month'])
    previous_month = datetime(*config['prev_month'])
    del config['month']
    del config['prev_month']

    this_month_data = get_data_for(current_month, config)
    prev_month_data = get_data_for(previous_month, config)

    return {
        'records': [
            [
                {
                    'label': _('AWCs with Clean Drinking Water'),
                    'help_text': _('Percentage of AWCs with a source of clean drinking water'),
                    'percent': percent_diff(
                        'clean_water',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'color': 'green' if percent_diff(
                        'clean_water',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'clean_water'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'clean_water'
                },
                {
                    'label': _("AWCs with Functional Toilet"),
                    'help_text': _('AWCs with functional toilet'),
                    'percent': percent_diff(
                        'functional_toilet',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'color': 'green' if percent_diff(
                        'functional_toilet',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'functional_toilet'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'functional_toilet'
                }
            ],
            [
                # {
                #     'label': _('AWCs with Electricity'),
                #     'help_text': _('Percentage of AWCs with access to electricity'),
                #     'percent': 0,
                #     'value': 0,
                #     'all': 0,
                #     'format': 'percent_and_div',
                #     'frequency': 'month'
                # },
                {
                    'label': _('AWCs with Weighing Scale: Infants'),
                    'help_text': _('Percentage of AWCs with weighing scale for infants'),
                    'percent': percent_diff(
                        'infant_scale',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'color': 'green' if percent_diff(
                        'infant_scale',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'infant_scale'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'infants_weight_scale'
                },
                {
                    'label': _('AWCs with Weighing Scale: Mother and Child'),
                    'help_text': _('Percentage of AWCs with weighing scale for mother and child'),
                    'percent': percent_diff(
                        'adult_scale',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'color': 'green' if percent_diff(
                        'adult_scale',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'adult_scale'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'adult_weight_scale'
                }
            ],
            [
                {
                    'label': _('AWCs with Medicine Kit'),
                    'help_text': _('Percentage of AWCs with a Medicine Kit'),
                    'percent': percent_diff(
                        'medicine_kits',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'color': 'green' if percent_diff(
                        'medicine_kits',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'medicine_kits'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'medicine_kit'
                }
            ],
            # [
            #     {
            #         'label': _('AWCs with infantometer'),
            #         'help_text': _('Percentage of AWCs with an Infantometer'),
            #         'percent': 0,
            #         'value': 0,
            #         'all': 0,
            #         'format': 'percent_and_div',
            #         'frequency': 'month'
            #     },
            #     {
            #         'label': _('AWCs with Stadiometer'),
            #         'help_text': _('Percentage of AWCs with a Stadiometer'),
            #         'percent': 0,
            #         'value': 0,
            #         'all': 0,
            #         'format': 'percent_and_div',
            #         'frequency': 'month'
            #     }
            # ]
        ]
    }
