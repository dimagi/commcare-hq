from __future__ import absolute_import
from __future__ import unicode_literals
from collections import OrderedDict
from datetime import datetime, timedelta, date

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule, DAILY, WEEKLY, MO

from django.db.models import F
from django.db.models.aggregates import Sum, Avg
from django.utils.translation import ugettext as _

from corehq.util.view_utils import absolute_reverse
from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.messages import wasting_help_text, stunting_help_text, \
    early_initiation_breastfeeding_help_text, exclusive_breastfeeding_help_text, \
    children_initiated_appropriate_complementary_feeding_help_text, institutional_deliveries_help_text, \
    percent_children_enrolled_help_text
from custom.icds_reports.models import AggAwcMonthly, DailyAttendanceView, \
    AggChildHealthMonthly, AggAwcDailyView, AggCcsRecordMonthly, ChildHealthMonthlyView
from custom.icds_reports.models.views import CcsRecordMonthlyView
from custom.icds_reports.utils import apply_exclude, percent_diff, get_value, percent_increase, \
    match_age, current_age, exclude_records_by_age_for_column, calculate_date_for_age, \
    person_has_aadhaar_column, person_is_beneficiary_column, get_status, wasting_moderate_column, \
    wasting_severe_column, stunting_moderate_column, stunting_severe_column, current_month_stunting_column, \
    current_month_wasting_column, hfa_recorded_in_month_column, wfh_recorded_in_month_column, \
    chosen_filters_to_labels, default_age_interval, get_anemic_status, get_symptoms, get_counseling, \
    get_tt_dates, is_anemic, format_decimal, DATA_NOT_ENTERED, get_delivery_nature, get_color_with_green_positive,\
    get_color_with_red_positive
from custom.icds_reports.const import MapColors
import six

from custom.icds_reports.messages import new_born_with_low_weight_help_text


@icds_quickcache(['domain', 'config', 'month', 'prev_month', 'two_before', 'loc_level', 'show_test'], timeout=30 * 60)
def get_awc_reports_system_usage(domain, config, month, prev_month, two_before, loc_level, show_test=False):

    def get_data_for(filters, date):
        queryset = AggAwcMonthly.objects.filter(
            month=datetime(*date), **filters
        ).values(
            loc_level
        ).annotate(
            awc_open=Sum('awc_days_open'),
            weighed=Sum('wer_weighed'),
            all=Sum('wer_eligible'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    chart_data = DailyAttendanceView.objects.filter(
        pse_date__range=(datetime(*two_before), datetime(*month)), **config
    ).values(
        'pse_date', 'aggregation_level'
    ).annotate(
        awc_count=Sum('awc_open_count'),
        attended_children=Avg('attended_children_percent')
    ).order_by('pse_date')

    if not show_test:
        chart_data = apply_exclude(domain, chart_data)

    awc_count_chart = []
    attended_children_chart = []
    for row in chart_data:
        date = row['pse_date']
        date_in_milliseconds = int(date.strftime("%s")) * 1000
        awc_count_chart.append([date_in_milliseconds, row['awc_count']])
        attended_children_chart.append([date_in_milliseconds, row['attended_children'] or 0])

    this_month_data = get_data_for(config, month)
    prev_month_data = get_data_for(config, prev_month)

    return {
        'kpi': [
            [
                {
                    'label': _('AWC Days Open'),
                    'help_text': _((
                        "The total number of days the AWC is open in the given month. The AWC is expected to "
                        "be open 6 days a week (Not on Sundays and public holidays)")
                    ),
                    'percent': percent_increase(
                        'awc_open',
                        this_month_data,
                        prev_month_data,
                    ),
                    'value': get_value(this_month_data, 'awc_open'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'month'
                },
                {
                    'label': _((
                        "Percentage of eligible children (ICDS beneficiaries between 0-6 years) "
                        "who have been weighed in the current month")
                    ),
                    'help_text': _('Percentage of AWCs with a functional toilet'),
                    'percent': percent_diff(
                        'weighed',
                        this_month_data,
                        prev_month_data,
                        'all'
                    ),
                    'value': get_value(this_month_data, 'weighed'),
                    'all': get_value(this_month_data, 'all'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                }
            ]
        ],
        'charts': [
            [
                {
                    'key': 'AWC Days Open Per Week',
                    'values': awc_count_chart,
                    "classed": "dashed",
                }
            ],
            [
                {
                    'key': 'PSE- Average Weekly Attendance',
                    'values': attended_children_chart,
                    "classed": "dashed",
                }
            ]
        ],
    }


@icds_quickcache(['config', 'month', 'domain', 'show_test'], timeout=30 * 60)
def get_awc_reports_pse(config, month, domain, show_test=False):
    selected_month = datetime(*month)
    last_months = (selected_month - relativedelta(months=1))
    last_day_of_selected_month = (selected_month + relativedelta(months=1)) - relativedelta(days=1)

    map_image_data = DailyAttendanceView.objects.filter(
        pse_date__range=(selected_month, last_day_of_selected_month), **config
    ).values(
        'awc_name', 'form_location_lat', 'form_location_long', 'image_name', 'doc_id', 'pse_date'
    ).order_by('-pse_date')

    kpi_data_tm = AggAwcMonthly.objects.filter(
        month=selected_month, **config
    ).values('awc_name').annotate(
        days_open=Sum('awc_days_open')
    )
    kpi_data_lm = AggAwcMonthly.objects.filter(
        month=last_months, **config
    ).values('awc_name').annotate(
        days_open=Sum('awc_days_open')
    )

    open_count_data = DailyAttendanceView.objects.filter(
        pse_date__range=(selected_month, last_day_of_selected_month), **config
    ).values('awc_name', 'pse_date').annotate(
        open_count=Sum('awc_open_count'),
    ).order_by('pse_date')

    daily_attendance = DailyAttendanceView.objects.filter(
        pse_date__range=(selected_month, last_day_of_selected_month), **config
    ).values('awc_name', 'pse_date').annotate(
        avg_percent=Avg('attended_children_percent'),
        attended=Sum('attended_children'),
        eligible=Sum('eligible_children')
    )

    if not show_test:
        map_image_data = apply_exclude(domain, map_image_data)
        kpi_data_tm = apply_exclude(domain, kpi_data_tm)
        kpi_data_lm = apply_exclude(domain, kpi_data_lm)
        open_count_data = apply_exclude(domain, open_count_data)
        daily_attendance = apply_exclude(domain, daily_attendance)

    attended_children_chart = {}
    dates = [dt for dt in rrule(DAILY, dtstart=selected_month, until=last_day_of_selected_month)]
    for date in dates:
        attended_children_chart[int(date.strftime("%s")) * 1000] = {
            'avg_percent': 0,
            'attended': 0,
            'eligible': 0
        }

    open_count_chart = {}

    open_count_dates = [
        dt for dt in rrule(WEEKLY, dtstart=selected_month, until=last_day_of_selected_month, byweekday=MO)
    ]
    for date in open_count_dates:
        first_day_of_week = date - timedelta(days=date.isoweekday() - 1)
        milliseconds = int(first_day_of_week.strftime("%s")) * 1000
        open_count_chart[milliseconds] = 0

    for chart_row in open_count_data:
        first_day_of_week = chart_row['pse_date'] - timedelta(days=chart_row['pse_date'].isoweekday() - 1)
        pse_week = int(first_day_of_week.strftime("%s")) * 1000

        if pse_week in open_count_chart:
            open_count_chart[pse_week] += (chart_row['open_count'] or 0)
        else:
            open_count_chart[pse_week] = (chart_row['open_count'] or 0)

    for daily_attendance_row in daily_attendance:
        pse_day = int(daily_attendance_row['pse_date'].strftime("%s")) * 1000
        attended_children_chart[pse_day] = {
            'avg_percent': daily_attendance_row['avg_percent'] or 0,
            'attended': daily_attendance_row['attended'] or 0,
            'eligible': daily_attendance_row['eligible'] or 0
        }

    map_data = {}

    date_to_image_data = {}

    for map_row in map_image_data:
        lat = map_row['form_location_lat']
        longitude = map_row['form_location_long']
        awc_name = map_row['awc_name']
        image_name = map_row['image_name']
        doc_id = map_row['doc_id']
        pse_date = map_row['pse_date']
        if lat and longitude:
            key = doc_id.replace('-', '')
            map_data.update({
                key: {
                    'lat': float(lat),
                    'lng': float(longitude),
                    'focus': 'true',
                    'message': awc_name,
                }
            })
        if image_name:
            date_str = pse_date.strftime("%d/%m/%Y")
            date_to_image_data[date_str] = map_row

    images = []
    tmp_image = []

    for idx, date in enumerate(rrule(DAILY, dtstart=selected_month, until=last_day_of_selected_month)):
        date_str = date.strftime("%d/%m/%Y")
        image_data = date_to_image_data.get(date_str)

        if image_data:
            image_name = image_data['image_name']
            doc_id = image_data['doc_id']

            tmp_image.append({
                'id': idx,
                'image': absolute_reverse('icds_image_accessor', args=(domain, doc_id, image_name)),
                'date': date_str
            })
        else:
            tmp_image.append({
                'id': idx,
                'image': None,
                'date': date_str
            })

        if (idx + 1) % 4 == 0:
            images.append(tmp_image)
            tmp_image = []

    if tmp_image:
        images.append(tmp_image)

    return {
        'kpi': [
            [
                {
                    'label': _('AWC Days Open'),
                    'help_text': _((
                        """
                        Total number of days the AWC is open in the given month.
                        The AWC is expected to be open 6 days a week (Not on Sundays and public holidays)
                        """
                    )),
                    'percent': percent_increase(
                        'days_open',
                        kpi_data_tm,
                        kpi_data_lm,
                    ),
                    'value': get_value(kpi_data_tm, 'days_open'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'month',
                    'color': get_color_with_green_positive(percent_increase(
                        'days_open',
                        kpi_data_tm,
                        kpi_data_lm,
                    )),
                }
            ]
        ],
        'charts': [
            [
                {
                    'key': 'AWC Days Open per week',
                    'values': sorted([
                        dict(
                            x=x_val,
                            y=y_val
                        ) for x_val, y_val in six.iteritems(open_count_chart)
                    ], key=lambda d: d['x']),
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": MapColors.BLUE
                }
            ],
            [
                {
                    'key': 'PSE - Daily Attendance',
                    'values': sorted([
                        dict(
                            x=x_val,
                            y=y_val['avg_percent'],
                            attended=y_val['attended'],
                            eligible=y_val['eligible']
                        ) for x_val, y_val in six.iteritems(attended_children_chart)
                    ], key=lambda d: d['x']),
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": MapColors.BLUE
                },
            ]
        ],
        'map': {
            'markers': map_data,
        },
        'images': images
    }


@icds_quickcache(['domain', 'config', 'month', 'prev_month', 'show_test', 'icds_feature_flag'], timeout=30 * 60)
def get_awc_reports_maternal_child(domain, config, month, prev_month, show_test=False, icds_feature_flag=False):

    def get_data_for(date):
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
            month=date, **config
        ).values(
            'month', 'aggregation_level'
        ).annotate(
            underweight=(
                Sum(moderately_underweight) + Sum(severely_underweight)
            ),
            valid_weighed=Sum(nutrition_status_weighed),
            immunized=(
                Sum('fully_immunized_on_time') + Sum('fully_immunized_late')
            ),
            eligible=Sum('fully_immunized_eligible'),
            wasting=Sum(wasting_moderate) + Sum(wasting_severe),
            height_measured_in_month=Sum(height_measured_in_month),
            weighed_and_height_measured_in_month=Sum(weighed_and_height_measured_in_month),
            stunting=Sum(stunting_moderate) + Sum(stunting_severe),
            low_birth=Sum('low_birth_weight_in_month'),
            birth=Sum('bf_at_birth'),
            born=Sum('born_in_month'),
            weighed_and_born_in_month=Sum('weighed_and_born_in_month'),
            month_ebf=Sum('ebf_in_month'),
            ebf=Sum('ebf_eligible'),
            month_cf=Sum('cf_initiation_in_month'),
            cf=Sum('cf_initiation_eligible')
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    def get_weight_efficiency(date):
        queryset = AggAwcMonthly.objects.filter(
            month=date, **config
        ).values(
            'month', 'aggregation_level', 'awc_name'
        ).annotate(
            wer_weight=Sum('wer_weighed'),
            wer_eli=Sum('wer_eligible')
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    def get_institutional_delivery_data(date):
        queryset = AggCcsRecordMonthly.objects.filter(
            month=date, **config
        ).values(
            'month', 'aggregation_level', 'awc_name'
        ).annotate(
            institutional_delivery_in_month_sum=Sum('institutional_delivery_in_month'),
            delivered_in_month_sum=Sum('delivered_in_month')
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    this_month_data = get_data_for(datetime(*month))
    prev_month_data = get_data_for(datetime(*prev_month))

    this_month_data_we = get_weight_efficiency(datetime(*month))
    prev_month_data_we = get_weight_efficiency(datetime(*prev_month))

    this_month_institutional_delivery_data = get_institutional_delivery_data(datetime(*month))
    prev_month_institutional_delivery_data = get_institutional_delivery_data(datetime(*prev_month))

    gender_label, age_label, chosen_filters = chosen_filters_to_labels(
        config,
        default_interval=default_age_interval(icds_feature_flag)
    )

    return {
        'kpi': [
            [
                {
                    'label': _('Underweight (Weight-for-Age)'),
                    'help_text': _((
                        "Of the total children weighed, the percentage of children between 0-5 years who were "
                        "moderately/severely underweight in the current month. Children who are moderately or "
                        "severely underweight have a higher risk of mortality. "
                    )),
                    'percent': percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid_weighed'
                    ),
                    'color': get_color_with_red_positive(percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid_weighed'
                    )),
                    'value': get_value(this_month_data, 'underweight'),
                    'all': get_value(this_month_data, 'valid_weighed'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Wasting (Weight-for-Height)'),
                    'help_text': wasting_help_text(age_label),
                    'percent': percent_diff(
                        'wasting',
                        this_month_data,
                        prev_month_data,
                        'weighed_and_height_measured_in_month'
                    ),
                    'color': get_color_with_red_positive(percent_diff(
                        'wasting',
                        this_month_data,
                        prev_month_data,
                        'weighed_and_height_measured_in_month'
                    )),
                    'value': get_value(this_month_data, 'wasting'),
                    'all': get_value(this_month_data, 'weighed_and_height_measured_in_month'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ],
            [
                {
                    'label': _('Stunting (Height-for-Age)'),
                    'help_text': stunting_help_text(age_label),
                    'percent': percent_diff(
                        'stunting',
                        this_month_data,
                        prev_month_data,
                        'height_measured_in_month'
                    ),
                    'color': get_color_with_red_positive(percent_diff(
                        'stunting',
                        this_month_data,
                        prev_month_data,
                        'height_measured_in_month'
                    )),
                    'value': get_value(this_month_data, 'stunting'),
                    'all': get_value(this_month_data, 'height_measured_in_month'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Weighing Efficiency'),
                    'help_text': _(
                        "Of the children between the ages of 0-5 years who are enrolled for Anganwadi Services, "
                        "the percentage who were weighed in the given month. "
                    ),
                    'percent': percent_diff(
                        'wer_weight',
                        this_month_data_we,
                        prev_month_data_we,
                        'wer_eli'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'wer_weight',
                        this_month_data_we,
                        prev_month_data_we,
                        'wer_eli'
                    )),
                    'value': get_value(this_month_data_we, 'wer_weight'),
                    'all': get_value(this_month_data_we, 'wer_eli'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },

            ],
            [
                {
                    'label': _('Newborns with Low Birth Weight'),
                    'help_text': _(
                        new_born_with_low_weight_help_text(html=False)
                    ),
                    'percent': percent_diff(
                        'low_birth',
                        this_month_data,
                        prev_month_data,
                        'weighed_and_born_in_month'
                    ),
                    'color': get_color_with_red_positive(percent_diff(
                        'low_birth',
                        this_month_data,
                        prev_month_data,
                        'weighed_and_born_in_month'
                    )),
                    'value': get_value(this_month_data, 'low_birth'),
                    'all': get_value(this_month_data, 'weighed_and_born_in_month'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Early Initiation of Breastfeeding'),
                    'help_text': early_initiation_breastfeeding_help_text(),
                    'percent': percent_diff(
                        'birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    )),
                    'value': get_value(this_month_data, 'birth'),
                    'all': get_value(this_month_data, 'born'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ],
            [
                {
                    'label': _('Exclusive breastfeeding'),
                    'help_text': exclusive_breastfeeding_help_text(),
                    'percent': percent_diff(
                        'month_ebf',
                        this_month_data,
                        prev_month_data,
                        'ebf'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'month_ebf',
                        this_month_data,
                        prev_month_data,
                        'ebf'
                    )),
                    'value': get_value(this_month_data, 'month_ebf'),
                    'all': get_value(this_month_data, 'ebf'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Children initiated appropriate Complementary Feeding'),
                    'help_text': children_initiated_appropriate_complementary_feeding_help_text(),
                    'percent': percent_diff(
                        'month_cf',
                        this_month_data,
                        prev_month_data,
                        'cf'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'month_cf',
                        this_month_data,
                        prev_month_data,
                        'cf'
                    )),
                    'value': get_value(this_month_data, 'month_cf'),
                    'all': get_value(this_month_data, 'cf'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ],
            [
                {
                    'label': _('Immunization Coverage (at age 1 year)'),
                    'help_text': _((
                        "Of the total number of children enrolled for Anganwadi Services who are over a year old, "
                        "the percentage of children who have received the complete immunization as per the "
                        "National Immunization Schedule of India that is required by age 1."
                        "<br/><br/> "
                        "This includes the following immunizations:<br/> "
                        "If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/> "
                        "If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1"
                    )),
                    'percent': percent_diff(
                        'immunized',
                        this_month_data,
                        prev_month_data,
                        'eligible'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'immunized',
                        this_month_data,
                        prev_month_data,
                        'eligible'
                    )),
                    'value': get_value(this_month_data, 'immunized'),
                    'all': get_value(this_month_data, 'eligible'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Institutional Deliveries'),
                    'help_text': institutional_deliveries_help_text(),
                    'percent': percent_diff(
                        'institutional_delivery_in_month_sum',
                        this_month_institutional_delivery_data,
                        prev_month_institutional_delivery_data,
                        'delivered_in_month_sum'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'institutional_delivery_in_month_sum',
                        this_month_institutional_delivery_data,
                        prev_month_institutional_delivery_data,
                        'delivered_in_month_sum'
                    )),
                    'value': get_value(
                        this_month_institutional_delivery_data,
                        'institutional_delivery_in_month_sum'
                    ),
                    'all': get_value(this_month_institutional_delivery_data, 'delivered_in_month_sum'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ]
        ]
    }


@icds_quickcache(['domain', 'config', 'now_date', 'month', 'show_test', 'beta'], timeout=30 * 60)
def get_awc_report_demographics(domain, config, now_date, month, show_test=False, beta=False):
    selected_month = datetime(*month)
    now_date = datetime(*now_date)
    chart = AggChildHealthMonthly.objects.filter(
        month=selected_month, **config
    ).values(
        'age_tranche', 'aggregation_level'
    ).annotate(
        valid=Sum('valid_in_month')
    ).order_by('age_tranche')

    if not show_test:
        chart = apply_exclude(domain, chart)

    chart_data = OrderedDict()
    chart_data.update({'0-1 month': 0})
    chart_data.update({'1-6 months': 0})
    chart_data.update({'6-12 months': 0})
    chart_data.update({'1-3 years': 0})
    chart_data.update({'3-6 years': 0})

    for chart_row in chart:
        if chart_row['age_tranche']:
            age = int(chart_row['age_tranche'])
            valid = chart_row['valid']
            chart_data[match_age(age)] += valid

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

    previous_month = selected_month - relativedelta(months=1)
    if selected_month.month == now_date.month and selected_month.year == now_date.year:
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
        config['month'] = selected_month
        data = get_data_for(AggAwcMonthly, config)
        config['month'] = previous_month
        prev_data = get_data_for(AggAwcMonthly, config)
        frequency = 'month'

    return {
        'chart': [
            {
                'key': 'Children (0-6 years)',
                'values': [[key, value] for key, value in six.iteritems(chart_data)],
                "classed": "dashed",
            }
        ],
        'kpi': [
            [
                {
                    'label': _('Registered Households'),
                    'help_text': _("Total number of households registered"),
                    'percent': percent_increase(
                        'household',
                        data,
                        prev_data,
                    ),
                    'color': get_color_with_green_positive(percent_increase(
                        'household',
                        data,
                        prev_data)),
                    'value': get_value(data, 'household'),
                    'all': '',
                    'format': 'number',
                    'frequency': frequency
                },
                {
                    'label': _('Percent Aadhaar-seeded Beneficiaries'),
                    'help_text': _(
                        'Of the total number of ICDS beneficiaries, the percentage whose Adhaar identification '
                        'has been captured. '
                    ),
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
                        'all_persons'
                    )),
                    'value': get_value(data, 'person_aadhaar'),
                    'all': get_value(data, 'all_persons'),
                    'format': 'percent_and_div',
                    'frequency': frequency
                }
            ],
            [
                {
                    'label': _('Percent children (0-6 years) enrolled for Anganwadi Services'),
                    'help_text': percent_children_enrolled_help_text(),
                    'percent': percent_diff('child_health', data, prev_data, 'child_health_all'),
                    'color': get_color_with_green_positive(percent_diff(
                        'child_health_all',
                        data,
                        prev_data, 'child_health_all')),
                    'value': get_value(data, 'child_health'),
                    'all': get_value(data, 'child_health_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency,
                },
                {
                    'label': _('Percent pregnant women enrolled for Anganwadi Services'),
                    'help_text': _('Of the total number of pregnant women, the percentage of pregnant '
                                   'women enrolled for Anganwadi Services'),
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
                    'frequency': frequency
                }
            ],
            [

                {
                    'label': _('Percent lactating women enrolled for Anganwadi Services'),
                    'help_text': _('Of the total number of lactating women, the percentage of '
                                   'lactating women enrolled for Anganwadi Services'),
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
                    'frequency': frequency
                },
                {
                    'label': _('Percent adolescent girls (11-14 years) enrolled for Anganwadi Services'),
                    'help_text': _((
                        "Of the total number of adolescent girls (aged 11-14 years), the percentage "
                        "of girls enrolled for Anganwadi Services"
                    )),
                    'percent': percent_diff(
                        'person_adolescent',
                        data,
                        prev_data,
                        'person_adolescent_all'
                    ),
                    'color': get_color_with_green_positive(percent_diff(
                        'person_adolescent',
                        data,
                        prev_data,
                        'person_adolescent_all'
                    )),
                    'value': get_value(data, 'person_adolescent'),
                    'all': get_value(data, 'person_adolescent_all'),
                    'format': 'percent_and_div',
                    'frequency': frequency
                }
            ]
        ]
    }


@icds_quickcache(['domain', 'config', 'month', 'show_test', 'beta'], timeout=30 * 60)
def get_awc_report_infrastructure(domain, config, month, show_test=False, beta=False):
    selected_month = datetime(*month)

    def get_data_for_kpi(filters, date):
        queryset = AggAwcMonthly.objects.filter(
            month=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            clean_water=Sum('infra_clean_water'),
            functional_toilet=Sum('infra_functional_toilet'),
            medicine_kits=Sum('infra_medicine_kits'),
            infant_weighing_scale=Sum('infra_infant_weighing_scale'),
            adult_weighing_scale=Sum('infra_adult_weighing_scale'),
            num_awc_infra_last_update=Sum('num_awc_infra_last_update'),
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    def get_infa_value(data, prop):
        if beta:
            value = data[0][prop] if data and data[0]['num_awc_infra_last_update'] else None
        else:
            value = (data[0][prop] or None) if data else None
        if value is not None:
            if value == 1:
                return _("Available")
            else:
                return _("Not Available")
        else:
            return _(DATA_NOT_ENTERED)

    kpi_data = get_data_for_kpi(config, selected_month.date())

    return {
        'kpi': [
            [
                {
                    'label': _('Clean Drinking Water'),
                    'help_text': None,
                    'value': get_infa_value(kpi_data, 'clean_water'),
                    'all': '',
                    'format': 'string',
                    'show_percent': False,
                    'frequency': 'month'
                },
                {
                    'label': _('Functional Toilet'),
                    'help_text': None,
                    'value': get_infa_value(kpi_data, 'functional_toilet'),
                    'all': '',
                    'format': 'string',
                    'show_percent': False,
                    'frequency': 'month'
                }
            ],
            [
                {
                    'label': _('Weighing Scale: Infants'),
                    'help_text': None,
                    'value': get_infa_value(kpi_data, 'infant_weighing_scale'),
                    'all': '',
                    'format': 'string',
                    'show_percent': False,
                    'frequency': 'month'
                },
                {
                    'label': _('AWCs with Weighing Scale: Mother and Child'),
                    'help_text': None,
                    'value': get_infa_value(kpi_data, 'adult_weighing_scale'),
                    'all': '',
                    'format': 'string',
                    'show_percent': False,
                    'frequency': 'month'
                }
            ],
            [
                {
                    'label': _('Medicine Kit'),
                    'help_text': None,
                    'value': get_infa_value(kpi_data, 'medicine_kits'),
                    'all': '',
                    'format': 'string',
                    'show_percent': False,
                    'frequency': 'month'
                }
            ],
        ]
    }


@icds_quickcache([
    'start', 'length', 'draw', 'order', 'filters', 'month', 'two_before', 'icds_features_flag'
], timeout=30 * 60)
def get_awc_report_beneficiary(start, length, draw, order, filters, month, two_before,
                               icds_features_flag):

    filters['month'] = datetime(*month)
    filters['open_in_month'] = 1
    filters['valid_in_month'] = 1
    if filters.get('age_in_months__in') is None:
        filters['age_in_months__lte'] = 60
    data = ChildHealthMonthlyView.objects.filter(
        **filters
    ).order_by(order)
    data_count = data.count()
    data = data[start:(start + length)]
    config = {
        'data': [],
        'months': [
            dt.strftime("%b %Y") for dt in rrule(
                MONTHLY,
                dtstart=datetime(*two_before),
                until=datetime(*month)
            )
        ][::-1],
        'last_month': datetime(*month).strftime("%b %Y"),
    }

    def base_data(row_data):
        return dict(
            case_id=row_data.case_id,
            person_name=row_data.person_name,
            dob=row_data.dob,
            age=calculate_date_for_age(row_data.dob, datetime(*month).date()),
            fully_immunized='Yes' if row_data.fully_immunized else 'No',
            age_in_months=row_data.age_in_months,
            current_month_nutrition_status=get_status(
                row_data.current_month_nutrition_status,
                'underweight',
                'Normal weight for age'
            ),
            recorded_weight=row_data.recorded_weight or 0,
            recorded_height=row_data.recorded_height or 0,
            current_month_stunting=get_status(
                getattr(row_data, current_month_stunting_column(icds_features_flag)),
                'stunted',
                'Normal height for age',
                data_entered=True if row_data.recorded_height else False
            ),
            current_month_wasting=get_status(
                getattr(row_data, current_month_wasting_column(icds_features_flag)),
                'wasted',
                'Normal weight for height',
                data_entered=True if row_data.recorded_height and row_data.recorded_weight else False
            ),
            pse_days_attended=row_data.pse_days_attended,
            mother_phone_number=row_data.mother_phone_number,
            aww_phone_number=row_data.aww_phone_number
        )

    for row in data:
        config['data'].append(base_data(row))

    config["draw"] = draw
    config["recordsTotal"] = data_count
    config["recordsFiltered"] = data_count

    return config


@icds_quickcache(['case_id', 'awc_id', 'selected_month'], timeout=30 * 60)
def get_beneficiary_details(case_id, awc_id, selected_month):
    selected_month = datetime(*selected_month)
    six_month_before = selected_month - relativedelta(months=6)
    data = ChildHealthMonthlyView.objects.filter(
        case_id=case_id,
        awc_id=awc_id,
        month__range=(six_month_before, selected_month)
    ).order_by('month')

    min_height = 35
    max_height = 120.0

    beneficiary = {
        'weight': [],
        'height': [],
        'wfl': []
    }
    for row in data:
        age_in_months = row.age_in_months
        recorded_weight = row.recorded_weight
        recorded_height = row.recorded_height
        beneficiary.update({
            'person_name': row.person_name,
            'mother_name': row.mother_name,
            'dob': row.dob,
            'age': current_age(row.dob, datetime.now().date()),
            'sex': row.sex,
            'age_in_months': age_in_months,
        })
        if age_in_months <= 60:
            if recorded_weight:
                beneficiary['weight'].append({
                    'x': int(age_in_months),
                    'y': float(recorded_weight)
                })
            if recorded_height:
                beneficiary['height'].append({
                    'x': int(age_in_months),
                    'y': float(recorded_height)
                })
        if recorded_height and min_height <= recorded_height <= max_height:
            beneficiary['wfl'].append({
                'x': float(row.recorded_height),
                'y': float(recorded_weight) if row.recorded_height else 0
            })
    return beneficiary


@icds_quickcache([
    'start', 'length', 'order', 'reversed_order', 'awc_id'
], timeout=30 * 60)
def get_awc_report_pregnant(start, length, order, reversed_order, awc_id):
    this_month = date.today() - relativedelta(day=1)
    data = CcsRecordMonthlyView.objects.filter(
        awc_id=awc_id,
        month=this_month,
        pregnant_all=1,
    ).order_by('case_id', '-month').distinct('case_id').values(
        'case_id', 'person_name', 'age_in_months', 'opened_on', 'edd', 'trimester', 'anemic_severe',
        'anemic_moderate', 'anemic_normal', 'anemic_unknown', 'num_anc_complete', 'pregnant_all',
        'num_rations_distributed', 'last_date_thr', 'month', 'closed', 'open_in_month', 'pregnant'
    ).exclude(open_in_month=False)
    data_count = data.count()
    config = {
        'data': [],
    }

    def base_data(row_data):
        return dict(
            case_id=row_data['case_id'],
            person_name=row_data['person_name'],
            age=row_data['age_in_months'] // 12 if row_data['age_in_months'] else row_data['age_in_months'],
            closed=row_data['closed'],
            opened_on=row_data['opened_on'],
            edd=row_data['edd'],
            trimester=row_data['trimester'],
            anemic=is_anemic(row_data),
            num_anc_complete=row_data['num_anc_complete'],
            beneficiary='Yes' if row_data['pregnant'] else 'No',
            number_of_thrs_given=row_data['num_rations_distributed'],
            last_date_thr=row_data['last_date_thr'],
        )

    for row in data:
        config['data'].append(base_data(row))

    def ordering_format(record):
        if record[order]:
            return record[order]
        numeric_fields = ['age', 'closed', 'trimester', 'num_anc_complete', 'number_of_thrs_given']
        if any([field in order for field in numeric_fields]):
            return 0
        date_fields = ['opened_on', 'edd', 'last_date_thr']
        if any([field in order for field in date_fields]):
            return date.today()
        return ""

    config['data'].sort(key=ordering_format, reverse=reversed_order)
    config['data'] = config['data'][start:(start + length)]
    config["recordsTotal"] = data_count
    config["recordsFiltered"] = data_count

    return config


@icds_quickcache(['case_id', 'awc_id'], timeout=30 * 60)
def get_pregnant_details(case_id, awc_id):
    ten_months_ago = datetime.utcnow() - relativedelta(months=10, day=1)
    data = CcsRecordMonthlyView.objects.filter(
        case_id=case_id,
        awc_id=awc_id,
        month__gte=ten_months_ago,
        home_visit_date__lte=F('month') + timedelta(days=31),
    ).order_by('home_visit_date', '-month').distinct('home_visit_date').values(
        'case_id', 'trimester', 'person_name', 'age_in_months', 'mobile_number', 'edd', 'opened_on', 'preg_order',
        'home_visit_date', 'bp_sys', 'bp_dia', 'anc_weight', 'anc_hemoglobin', 'anemic_severe', 'anemic_moderate',
        'anemic_normal', 'anemic_unknown', 'bleeding', 'swelling', 'blurred_vision', 'convulsions', 'rupture',
        'eating_extra', 'resting', 'immediate_breastfeeding', 'using_ifa',
        'ifa_consumed_last_seven_days', 'tt_1', 'tt_2', 'month', 'anc_abnormalities'
    )

    config = {
        'data': [
            [],
            [],
            [],
        ],
    }
    for row_data in data:
        config['data'][row_data['trimester'] - 1].append(
            dict(
                case_id=row_data['case_id'],
                trimester=row_data['trimester'] if row_data['trimester'] else DATA_NOT_ENTERED,
                person_name=row_data['person_name'] if row_data['person_name'] else DATA_NOT_ENTERED,
                age=row_data['age_in_months'] // 12 if row_data['age_in_months'] else row_data['age_in_months'],
                mobile_number=row_data['mobile_number'] if row_data['mobile_number'] else DATA_NOT_ENTERED,
                edd=row_data['edd'] if row_data['edd'] else DATA_NOT_ENTERED,
                opened_on=row_data['opened_on'] if row_data['opened_on'] else DATA_NOT_ENTERED,
                preg_order=row_data['preg_order'] if row_data['preg_order'] else DATA_NOT_ENTERED,
                home_visit_date=row_data['home_visit_date'] if row_data['home_visit_date'] else DATA_NOT_ENTERED,
                bp=DATA_NOT_ENTERED if not row_data['bp_sys'] and not row_data['bp_dia'] else '{} / {}'.format(
                    row_data['bp_sys'] if row_data['bp_sys'] else DATA_NOT_ENTERED,
                    row_data['bp_dia'] if row_data['bp_dia'] else DATA_NOT_ENTERED,
                ),
                anc_weight=row_data['anc_weight'] if row_data['anc_weight'] else DATA_NOT_ENTERED,
                anc_hemoglobin=format_decimal(
                    row_data['anc_hemoglobin']
                ) if row_data['anc_hemoglobin'] else DATA_NOT_ENTERED,
                anc_abnormalities='Yes' if row_data['anc_abnormalities'] else 'None',
                anemic=get_anemic_status(row_data),
                symptoms=get_symptoms(row_data),
                counseling=get_counseling(row_data),
                using_ifa='Y' if row_data['using_ifa'] else 'N',
                ifa_consumed_last_seven_days='Y' if row_data['ifa_consumed_last_seven_days'] else 'N',
                tt_taken='Y' if get_tt_dates(row_data) != 'None' else 'N',
                tt_date=get_tt_dates(row_data),
            )
        )
        if not config.get('pregnant', None):
            config['pregnant'] = {
                'person_name': row_data['person_name'] if row_data['person_name'] else DATA_NOT_ENTERED,
                'age': row_data['age_in_months'] // 12 if row_data['age_in_months'] else row_data['age_in_months'],
                'mobile_number': row_data['mobile_number'] if row_data['mobile_number'] else DATA_NOT_ENTERED,
                'edd': row_data['edd'] if row_data['edd'] else DATA_NOT_ENTERED,
                'opened_on': row_data['opened_on'] if row_data['opened_on'] else DATA_NOT_ENTERED,
                'trimester': row_data['trimester'] if row_data['trimester'] else DATA_NOT_ENTERED,
                'preg_order': row_data['preg_order'] if row_data['preg_order'] else DATA_NOT_ENTERED,
            }
    if not config.get('pregnant', None):
        row_data = CcsRecordMonthlyView.objects.filter(
            case_id=case_id,
            awc_id=awc_id,
            month__gte=ten_months_ago,
        ).order_by('case_id', '-month').distinct('case_id').values(
            'case_id', 'trimester', 'person_name', 'age_in_months', 'mobile_number', 'edd', 'opened_on',
            'preg_order', 'home_visit_date'
        ).first()
        config['pregnant'] = {
            'person_name': row_data['person_name'] if row_data['person_name'] else DATA_NOT_ENTERED,
            'age': row_data['age_in_months'] // 12 if row_data['age_in_months'] else row_data['age_in_months'],
            'mobile_number': row_data['mobile_number'] if row_data['mobile_number'] else DATA_NOT_ENTERED,
            'edd': row_data['edd'] if row_data['edd'] else DATA_NOT_ENTERED,
            'opened_on': row_data['opened_on'] if row_data['opened_on'] else DATA_NOT_ENTERED,
            'trimester': row_data['trimester'] if row_data['trimester'] else DATA_NOT_ENTERED,
            'preg_order': row_data['preg_order'] if row_data['preg_order'] else DATA_NOT_ENTERED,
        }
    return config


@icds_quickcache([
    'start', 'length', 'order', 'reversed_order', 'awc_id'
], timeout=30 * 60)
def get_awc_report_lactating(start, length, order, reversed_order, awc_id):
    one_month_ago = datetime.utcnow() - relativedelta(months=1, day=1)
    data = CcsRecordMonthlyView.objects.filter(
        awc_id=awc_id,
        month__gte=one_month_ago,
    ).order_by('case_id', '-month').distinct('case_id').values(
        'case_id', 'lactating', 'open_in_month', 'date_death'
    ).filter(lactating=1, date_death=None).exclude(open_in_month=False)

    case_ids = [case['case_id'] for case in data]
    if case_ids:
        data = CcsRecordMonthlyView.objects.filter(
            awc_id=awc_id,
            month__gte=one_month_ago,
            date_death=None,
            case_id__in=case_ids,
        ).order_by('case_id', '-month').distinct('case_id').values(
            'case_id', 'person_name', 'age_in_months', 'add', 'delivery_nature', 'institutional_delivery',
            'num_pnc_visits', 'breastfed_at_birth', 'is_ebf', 'num_rations_distributed', 'month'
        )
        data_count = data.count()
    else:
        data = []
        data_count = 0

    config = {
        'data': [],
    }

    def base_data(row_data):
        return dict(
            case_id=row_data['case_id'],
            person_name=row_data['person_name'],
            age=row_data['age_in_months'] // 12 if row_data['age_in_months'] else row_data['age_in_months'],
            add=row_data['add'],
            delivery_nature=get_delivery_nature(row_data),
            institutional_delivery='Y' if row_data['institutional_delivery'] else 'N',
            num_pnc_visits=row_data['num_pnc_visits'],
            breastfed_at_birth='Y' if row_data['breastfed_at_birth'] else 'N',
            is_ebf='Y' if row_data['is_ebf'] else 'N',
            num_rations_distributed=row_data['num_rations_distributed'],
        )

    for row in data:
        config['data'].append(base_data(row))

    def ordering_format(record):
        if record[order]:
            return record[order]
        numeric_fields = ['age', 'delivery_nature', 'num_pnc_visits', 'num_rations_distributed']
        if any([field in order for field in numeric_fields]):
            return 0
        date_fields = ['add']
        if any([field in order for field in date_fields]):
            return date.today()
        return ""

    config['data'].sort(key=ordering_format, reverse=reversed_order)
    config['data'] = config['data'][start:(start + length)]
    config["recordsTotal"] = data_count
    config["recordsFiltered"] = data_count

    return config
