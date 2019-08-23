from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from custom.icds_reports.messages import awcs_reported_clean_drinking_water_help_text, \
    awcs_reported_functional_toilet_help_text, awcs_reported_weighing_scale_infants_help_text, \
    awcs_reported_weighing_scale_mother_and_child_help_text, awcs_reported_medicine_kit_help_text
from custom.icds_reports.models import AggAwcMonthly
from custom.icds_reports.utils import apply_exclude, percent_diff, get_value, get_color_with_green_positive


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
            sum_last_update=Sum('num_awc_infra_last_update')
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
                    'label': _('AWCs Reported Clean Drinking Water'),
                    'help_text': awcs_reported_clean_drinking_water_help_text(),
                    'percent': percent_diff(
                        'clean_water',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'clean_water',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    )),
                    'value': get_value(this_month_data, 'clean_water'),
                    'all': get_value(this_month_data, 'sum_last_update'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'awc_infrastructure/clean_water'
                },
                {
                    'label': _("AWCs Reported Functional Toilet"),
                    'help_text': awcs_reported_functional_toilet_help_text(),
                    'percent': percent_diff(
                        'functional_toilet',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'functional_toilet',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    )),
                    'value': get_value(this_month_data, 'functional_toilet'),
                    'all': get_value(this_month_data, 'sum_last_update'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'awc_infrastructure/functional_toilet'
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
                    'label': _('AWCs Reported Weighing Scale: Infants'),
                    'help_text': awcs_reported_weighing_scale_infants_help_text(),
                    'percent': percent_diff(
                        'infant_scale',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'infant_scale',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    )),
                    'value': get_value(this_month_data, 'infant_scale'),
                    'all': get_value(this_month_data, 'sum_last_update'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'awc_infrastructure/infants_weight_scale'
                },
                {
                    'label': _('AWCs Reported Weighing Scale: Mother and Child'),
                    'help_text': awcs_reported_weighing_scale_mother_and_child_help_text(),
                    'percent': percent_diff(
                        'adult_scale',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'adult_scale',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    )),
                    'value': get_value(this_month_data, 'adult_scale'),
                    'all': get_value(this_month_data, 'sum_last_update'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'awc_infrastructure/adult_weight_scale'
                }
            ],
            [
                {
                    'label': _('AWCs Reported Medicine Kit'),
                    'help_text': awcs_reported_medicine_kit_help_text(),
                    'percent': percent_diff(
                        'medicine_kits',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'medicine_kits',
                        this_month_data,
                        prev_month_data,
                        'sum_last_update'
                    )),
                    'value': get_value(this_month_data, 'medicine_kits'),
                    'all': get_value(this_month_data, 'sum_last_update'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'awc_infrastructure/medicine_kit'
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
