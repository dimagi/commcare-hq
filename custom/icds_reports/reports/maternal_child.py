from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from corehq.util.quickcache import quickcache
from custom.icds_reports.messages import wasting_help_text, stunting_help_text
from custom.icds_reports.models import AggChildHealthMonthly, AggCcsRecordMonthly
from custom.icds_reports.utils import percent_diff, get_value, apply_exclude, exclude_records_by_age_for_column, \
    wasting_moderate_column, wasting_severe_column, stunting_moderate_column, stunting_severe_column, \
    hfa_recorded_in_month_column, wfh_recorded_in_month_column, chosen_filters_to_labels, default_age_interval


@quickcache(['domain', 'config', 'show_test', 'icds_feature_flag'], timeout=30 * 60)
def get_maternal_child_data(domain, config, show_test=False, icds_feature_flag=False):

    def get_data_for_child_health_monthly(date, filters):

        age_filters = {'age_tranche': 72} if icds_feature_flag else {'age_tranche__in': [0, 6, 72]}

        moderately_underweight = exclude_records_by_age_for_column(
            {'age_tranche': 72},
            'nutrition_status_moderately_underweight'
        )
        severely_underweight = exclude_records_by_age_for_column(
            {'age_tranche': 72},
            'nutrition_status_severely_underweight'
        )
        wasting_moderate = exclude_records_by_age_for_column(
            age_filters,
            wasting_moderate_column(icds_feature_flag)
        )
        wasting_severe = exclude_records_by_age_for_column(
            age_filters,
            wasting_severe_column(icds_feature_flag)
        )
        stunting_moderate = exclude_records_by_age_for_column(
            age_filters,
            stunting_moderate_column(icds_feature_flag)
        )
        stunting_severe = exclude_records_by_age_for_column(
            age_filters,
            stunting_severe_column(icds_feature_flag)
        )
        nutrition_status_weighed = exclude_records_by_age_for_column(
            {'age_tranche': 72},
            'nutrition_status_weighed'
        )
        height_measured_in_month = exclude_records_by_age_for_column(
            age_filters,
            hfa_recorded_in_month_column(icds_feature_flag)
        )
        weighed_and_height_measured_in_month = exclude_records_by_age_for_column(
            age_filters,
            wfh_recorded_in_month_column(icds_feature_flag)
        )

        queryset = AggChildHealthMonthly.objects.filter(
            month=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            underweight=(
                Sum(moderately_underweight) + Sum(severely_underweight)
            ),
            valid=Sum(nutrition_status_weighed),
            wasting=Sum(wasting_moderate) + Sum(wasting_severe),
            stunting=Sum(stunting_moderate) + Sum(stunting_severe),
            height_measured_in_month=Sum(height_measured_in_month),
            weighed_and_height_measured_in_month=Sum(weighed_and_height_measured_in_month),
            low_birth_weight=Sum('low_birth_weight_in_month'),
            bf_birth=Sum('bf_at_birth'),
            born=Sum('born_in_month'),
            weighed_and_born_in_month=Sum('weighed_and_born_in_month'),
            ebf=Sum('ebf_in_month'),
            ebf_eli=Sum('ebf_eligible'),
            cf_initiation=Sum('cf_initiation_in_month'),
            cf_initiation_eli=Sum('cf_initiation_eligible')
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    def get_data_for_deliveries(date, filters):
        queryset = AggCcsRecordMonthly.objects.filter(
            month=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            institutional_delivery=Sum('institutional_delivery_in_month'),
            delivered=Sum('delivered_in_month')
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    current_month = datetime(*config['month'])
    previous_month = datetime(*config['prev_month'])
    del config['month']
    del config['prev_month']

    this_month_data = get_data_for_child_health_monthly(current_month, config)
    prev_month_data = get_data_for_child_health_monthly(previous_month, config)

    deliveries_this_month = get_data_for_deliveries(current_month, config)
    deliveries_prev_month = get_data_for_deliveries(previous_month, config)

    gender_label, age_label, chosen_filters = chosen_filters_to_labels(
        config,
        default_interval=default_age_interval(icds_feature_flag)
    )

    return {
        'records': [
            [
                {
                    'label': _('Underweight (Weight-for-Age)'),
                    'help_text': _((
                        "Percentage of children between 0-5 years enrolled for Anganwadi Services with "
                        "weight-for-age less than -2 standard deviations of the WHO Child Growth Standards "
                        "median. Children who are moderately or severely underweight have a higher risk of "
                        "mortality."
                    )),
                    'percent': percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid'
                    ),
                    'color': 'red' if percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid'
                    ) > 0 else 'green',
                    'value': get_value(this_month_data, 'underweight'),
                    'all': get_value(this_month_data, 'valid'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'underweight_children'
                },
                {
                    'label': _('Wasting (Weight-for-Height)'),
                    'help_text': _(wasting_help_text(icds_feature_flag, age_label)),
                    'percent': percent_diff(
                        'wasting',
                        this_month_data,
                        prev_month_data,
                        'weighed_and_height_measured_in_month'
                    ),
                    'color': 'red' if percent_diff(
                        'wasting',
                        this_month_data,
                        prev_month_data,
                        'weighed_and_height_measured_in_month'
                    ) > 0 else 'green',
                    'value': get_value(this_month_data, 'wasting'),
                    'all': get_value(this_month_data, 'weighed_and_height_measured_in_month'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'wasting'
                }
            ],
            [
                {
                    'label': _('Stunting (Height-for-Age)'),
                    'help_text': _(stunting_help_text(icds_feature_flag, age_label)),
                    'percent': percent_diff(
                        'stunting',
                        this_month_data,
                        prev_month_data,
                        'height_measured_in_month'
                    ),
                    'color': 'red' if percent_diff(
                        'stunting',
                        this_month_data,
                        prev_month_data,
                        'height_measured_in_month'
                    ) > 0 else 'green',
                    'value': get_value(this_month_data, 'stunting'),
                    'all': get_value(this_month_data, 'height_measured_in_month'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'stunting'
                },
                {
                    'label': _('Newborns with Low Birth Weight'),
                    'help_text': _((
                        "Percentage of newborns born with birth weight less than 2500 grams. Newborns with"
                        " Low Birth Weight are closely associated with foetal and neonatal mortality and "
                        "morbidity, inhibited growth and cognitive development, and chronic diseases later "
                        "in life")),
                    'percent': percent_diff(
                        'low_birth_weight',
                        this_month_data,
                        prev_month_data,
                        'weighed_and_born_in_month'
                    ),
                    'color': 'red' if percent_diff(
                        'low_birth_weight',
                        this_month_data,
                        prev_month_data,
                        'weighed_and_born_in_month'
                    ) > 0 else 'green',
                    'value': get_value(this_month_data, 'low_birth_weight'),
                    'all': get_value(this_month_data, 'weighed_and_born_in_month'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'low_birth'
                }
            ],
            [
                {
                    'label': _('Early Initiation of Breastfeeding'),
                    'help_text': _((
                        "Percentage of children breastfed within an hour of birth. Early initiation of "
                        "breastfeeding ensure the newborn receives the 'first milk' rich in nutrients "
                        "and encourages exclusive breastfeeding practice")
                    ),
                    'percent': percent_diff(
                        'bf_birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'color': 'green' if percent_diff(
                        'bf_birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'bf_birth'),
                    'all': get_value(this_month_data, 'born'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'early_initiation'
                },
                {
                    'label': _('Exclusive Breastfeeding'),
                    'help_text': _((
                        "Percentage of children between 0 - 6 months exclusively breastfed. An infant is "
                        "exclusively breastfed if they receive only breastmilk with no additional food, "
                        "liquids (even water) ensuring optimal nutrition and growth between 0 - 6 months")
                    ),
                    'percent': percent_diff(
                        'ebf',
                        this_month_data,
                        prev_month_data,
                        'ebf_eli'
                    ),
                    'color': 'green' if percent_diff(
                        'ebf',
                        this_month_data,
                        prev_month_data,
                        'ebf_eli'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'ebf'),
                    'all': get_value(this_month_data, 'ebf_eli'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'exclusive_breastfeeding'
                }
            ],
            [
                {
                    'label': _('Children initiated appropriate Complementary Feeding'),
                    'help_text': _((
                        "Percentage of children between 6 - 8 months given timely introduction to solid or "
                        "semi-solid food. Timely initiation of complementary feeding in addition to "
                        "breastmilk at 6 months of age is a key feeding practice to reduce malnutrition")
                    ),
                    'percent': percent_diff(
                        'cf_initiation',
                        this_month_data,
                        prev_month_data,
                        'cf_initiation_eli'
                    ),
                    'color': 'green' if percent_diff(
                        'cf_initiation',
                        this_month_data,
                        prev_month_data,
                        'cf_initiation_eli'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'cf_initiation'),
                    'all': get_value(this_month_data, 'cf_initiation_eli'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'children_initiated'
                },
                {
                    'label': _('Institutional Deliveries'),
                    'help_text': _((
                        "Percentage of pregnant women who delivered in a public or private medical facility "
                        "in the last month. Delivery in medical institutions is associated with a "
                        "decrease in maternal mortality rate")
                    ),
                    'percent': percent_diff(
                        'institutional_delivery',
                        deliveries_this_month,
                        deliveries_prev_month,
                        'delivered'
                    ),
                    'color': 'green' if percent_diff(
                        'institutional_delivery',
                        deliveries_this_month,
                        deliveries_prev_month,
                        'delivered'
                    ) > 0 else 'red',
                    'value': get_value(deliveries_this_month, 'institutional_delivery'),
                    'all': get_value(deliveries_this_month, 'delivered'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'institutional_deliveries'
                }
            ]
        ]
    }
