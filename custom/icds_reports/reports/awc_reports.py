from collections import OrderedDict
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule, DAILY

from django.db.models.aggregates import Sum, Avg
from django.utils.translation import ugettext as _

from corehq.util.view_utils import absolute_reverse
from custom.icds_reports.models import ChildHealthMonthlyView, AggAwcMonthly, DailyAttendanceView, \
    AggChildHealthMonthly, AggAwcDailyView
from custom.icds_reports.utils import apply_exclude, percent_diff, get_value, percent_increase, match_age

RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'


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


def get_awc_reports_pse(config, month, domain, show_test=False):
    now = datetime.utcnow()
    last_30_days = (now - relativedelta(days=30))
    selected_month = datetime(*month)
    last_months = (selected_month - relativedelta(months=1))
    last_three_months = (selected_month - relativedelta(months=3))
    last_day_of_next_month = (selected_month + relativedelta(months=1)) - relativedelta(days=1)

    map_image_data = DailyAttendanceView.objects.filter(
        pse_date__range=(last_30_days, now), **config
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
        pse_date__range=(last_three_months, last_day_of_next_month), **config
    ).values('awc_name', 'pse_date').annotate(
        open_count=Sum('awc_open_count'),
    ).order_by('pse_date')

    daily_attendance = DailyAttendanceView.objects.filter(
        pse_date__range=(selected_month, last_day_of_next_month), **config
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
    dates = [dt for dt in rrule(DAILY, dtstart=selected_month, until=last_day_of_next_month)]
    for date in dates:
        attended_children_chart[int(date.strftime("%s")) * 1000] = {
            'avg_percent': 0,
            'attended': 0,
            'eligible': 0
        }

    open_count_chart = {}
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
        long = map_row['form_location_long']
        awc_name = map_row['awc_name']
        image_name = map_row['image_name']
        doc_id = map_row['doc_id']
        pse_date = map_row['pse_date']
        if lat and long:
            key = doc_id.replace('-', '')
            map_data.update({
                key: {
                    'lat': float(lat),
                    'lng': float(long),
                    'focus': 'true',
                    'message': awc_name,
                }
            })
        if image_name:
            date_str = pse_date.strftime("%d/%m/%Y")
            date_to_image_data[date_str] = map_row

    images = []
    tmp_image = []

    for idx, date in enumerate(rrule(DAILY, dtstart=last_30_days, until=now)):
        date_str = date.strftime("%d/%m/%Y")
        image_data = date_to_image_data.get(date_str)

        if image_data:
            image_name = image_data['image_name']
            doc_id = image_data['doc_id']

            tmp_image.append({
                'id': idx,
                'image': absolute_reverse('api_form_attachment', args=(domain, doc_id, image_name)),
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
                    'color': 'green' if percent_increase(
                        'days_open',
                        kpi_data_tm,
                        kpi_data_lm,
                    ) > 0 else 'red',
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
                        ) for x_val, y_val in open_count_chart.iteritems()
                    ], key=lambda d: d['x']),
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": BLUE
                }
            ],
            [
                {
                    'key': 'PSE - Average Daily Attendance',
                    'values': sorted([
                        dict(
                            x=x_val,
                            y=y_val['avg_percent'],
                            attended=y_val['attended'],
                            eligible=y_val['eligible']
                        ) for x_val, y_val in attended_children_chart.iteritems()
                    ], key=lambda d: d['x']),
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "color": BLUE
                },
            ]
        ],
        'map': {
            'markers': map_data,
        },
        'images': images
    }


def get_awc_reports_maternal_child(domain, config, month, prev_month, show_test=False):

    def get_data_for(date):
        queryset = AggChildHealthMonthly.objects.filter(
            month=date, **config
        ).values(
            'month', 'aggregation_level'
        ).annotate(
            underweight=(
                Sum('nutrition_status_moderately_underweight') + Sum('nutrition_status_severely_underweight')
            ),
            valid_in_month=Sum('valid_in_month'),
            immunized=(
                Sum('fully_immunized_on_time') + Sum('fully_immunized_late')
            ),
            eligible=Sum('fully_immunized_eligible'),
            wasting=(
                Sum('wasting_moderate') + Sum('wasting_severe')
            ),
            height=Sum('height_eligible'),
            stunting=(
                Sum('stunting_moderate') + Sum('stunting_severe')
            ),
            low_birth=Sum('low_birth_weight_in_month'),
            birth=Sum('bf_at_birth'),
            born=Sum('born_in_month'),
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

    this_month_data = get_data_for(datetime(*month))
    prev_month_data = get_data_for(datetime(*prev_month))

    this_month_data_we = get_weight_efficiency(datetime(*month))
    prev_month_data_we = get_weight_efficiency(datetime(*prev_month))

    return {
        'kpi': [
            [
                {
                    'label': _('Underweight (Weight-for-Age)'),
                    'help_text': _((
                        """
                        Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age
                        less than -2 standard deviations of the WHO Child Growth Standards median.
                        Children who are moderately or severely underweight have a higher risk of mortality.
                        """
                    )),
                    'percent': percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid_in_month'
                    ),
                    'color': 'red' if percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid_in_month'
                    ) > 0 else 'green',
                    'value': get_value(this_month_data, 'underweight'),
                    'all': get_value(this_month_data, 'valid_in_month'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Wasting (Weight-for-Height)'),
                    'help_text': _((
                        """
                        Percentage of children between 6 - 60 months enrolled for
                        ICDS services with weight-for-height
                        below -2 standard deviations of the WHO Child Growth Standards median.

                        Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute
                        undernutrition usually as a consequence
                        of insufficient food intake or a high incidence of infectious diseases.
                        """
                    )),
                    'percent': percent_diff(
                        'wasting',
                        this_month_data,
                        prev_month_data,
                        'height'
                    ),
                    'color': 'red' if percent_diff(
                        'wasting',
                        this_month_data,
                        prev_month_data,
                        'height'
                    ) > 0 else 'green',
                    'value': get_value(this_month_data, 'wasting'),
                    'all': get_value(this_month_data, 'height'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ],
            [
                {
                    'label': _('Stunting (Height-for-Age)'),
                    'help_text': _((
                        """
                            Percentage of children (6-60 months) with height-for-age below -2Z
                            standard deviations of the WHO Child Growth Standards median.
                            Stunting in children is a sign of chronic undernutrition and
                            has long lasting harmful consequences on the growth of a child
                        """
                    )),
                    'percent': percent_diff(
                        'stunting',
                        this_month_data,
                        prev_month_data,
                        'height'
                    ),
                    'color': 'red' if percent_diff(
                        'stunting',
                        this_month_data,
                        prev_month_data,
                        'height'
                    ) > 0 else 'green',
                    'value': get_value(this_month_data, 'stunting'),
                    'all': get_value(this_month_data, 'height'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Weighing Efficiency'),
                    'help_text': _((
                        """
                        Percentage of children (0-5 years) who
                        have been weighed of total children enrolled for ICDS services
                        """
                    )),
                    'percent': percent_diff(
                        'wer_weight',
                        this_month_data_we,
                        prev_month_data_we,
                        'wer_eli'
                    ),
                    'color': 'green' if percent_diff(
                        'wer_weight',
                        this_month_data_we,
                        prev_month_data_we,
                        'wer_eli'
                    ) > 0 else 'red',
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
                        """
                        Percentage of newborns born with birth weight less than 2500 grams.
                        Newborns with Low Birth Weight are closely associated with foetal and
                        neonatal mortality and morbidity, inhibited growth and cognitive development,
                        and chronic diseases later in life"
                        """
                    ),
                    'percent': percent_diff(
                        'low_birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'color': 'red' if percent_diff(
                        'low_birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ) > 0 else 'green',
                    'value': get_value(this_month_data, 'low_birth'),
                    'all': get_value(this_month_data, 'born'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Early Initiation of Breastfeeding'),
                    'help_text': _(
                        """
                        Percentage of children who were put to the breast within one hour of birth.

                        Early initiation of breastfeeding ensure the newborn recieves the ""first milk""
                        rich in nutrients and encourages exclusive breastfeeding practic
                        """
                    ),
                    'percent': percent_diff(
                        'birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'color': 'green' if percent_diff(
                        'birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'birth'),
                    'all': get_value(this_month_data, 'born'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ],
            [
                {
                    'label': _('Exclusive breastfeeding'),
                    'help_text': _(
                        """
                        Percentage of infants 0-6 months of age who are fed exclusively with breast milk.
                        An infant is exclusively breastfed if they recieve only breastmilk
                        with no additional food, liquids (even water) ensuring
                        optimal nutrition and growth between 0 - 6 months"
                        """
                    ),
                    'percent': percent_diff(
                        'month_ebf',
                        this_month_data,
                        prev_month_data,
                        'ebf'
                    ),
                    'color': 'green' if percent_diff(
                        'month_ebf',
                        this_month_data,
                        prev_month_data,
                        'ebf'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'month_ebf'),
                    'all': get_value(this_month_data, 'ebf'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Children initiated appropriate Complementary Feeding'),
                    'help_text': _(
                        """
                        Percentage of children between 6 - 8 months given timely introduction to solid,
                        semi-solid or soft food.
                        Timely intiation of complementary feeding in addition to breastmilk
                        at 6 months of age is a key feeding practice to reduce malnutrition"
                        """
                    ),
                    'percent': percent_diff(
                        'month_cf',
                        this_month_data,
                        prev_month_data,
                        'cf'
                    ),
                    'color': 'green' if percent_diff(
                        'month_cf',
                        this_month_data,
                        prev_month_data,
                        'cf'
                    ) > 0 else 'red',
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
                        """
                        Percentage of children 1 year+ who have recieved complete immunization as per
                        National Immunization Schedule of India required by age 1.
                        """
                    )),
                    'percent': percent_diff(
                        'immunized',
                        this_month_data,
                        prev_month_data,
                        'eligible'
                    ),
                    'color': 'green' if percent_diff(
                        'immunized',
                        this_month_data,
                        prev_month_data,
                        'eligible'
                    ) > 0 else 'red',
                    'value': get_value(this_month_data, 'immunized'),
                    'all': get_value(this_month_data, 'eligible'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ]
        ]
    }


def get_awc_report_demographics(domain, config, month, show_test=False):
    selected_month = datetime(*month)

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

    def get_data_for_kpi(filters, date):
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
            all_persons=Sum('cases_person_beneficiary')
        )
        if not show_test:
            queryset = apply_exclude(domain, queryset)
        return queryset

    yesterday = datetime.now() - relativedelta(days=1)
    two_days_ago = yesterday - relativedelta(days=1)
    kpi_yesterday = get_data_for_kpi(config, yesterday.date())
    kpi_two_days_ago = get_data_for_kpi(config, two_days_ago.date())

    return {
        'chart': [
            {
                'key': 'Children (0-6 years)',
                'values': [[key, value] for key, value in chart_data.iteritems()],
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
                        kpi_yesterday,
                        kpi_two_days_ago,
                    ),
                    'color': 'green' if percent_increase(
                        'household',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'household'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'month'
                },
                {
                    'label': _('Children (0-6 years)'),
                    'help_text': _('Total number of children registered between the age of 0 - 6 years'),
                    'percent': percent_increase('child_health_all', kpi_yesterday, kpi_two_days_ago),
                    'color': 'green' if percent_increase(
                        'child_health_all',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'child_health_all'),
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
                    'percent': percent_increase('child_health', kpi_yesterday, kpi_two_days_ago),
                    'color': 'green' if percent_increase(
                        'child_health',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'child_health'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Pregnant Women'),
                    'help_text': _("Total number of pregnant women registered"),
                    'percent': percent_increase(
                        'ccs_pregnant_all',
                        kpi_yesterday,
                        kpi_two_days_ago,
                    ),
                    'color': 'green' if percent_increase(
                        'ccs_pregnant_all',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'ccs_pregnant_all'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'day'
                },
            ],
            [
                {
                    'label': _('Pregnant Women enrolled for ICDS services'),
                    'help_text': _('Total number of pregnant women registered and enrolled for ICDS services'),
                    'percent': percent_increase('ccs_pregnant', kpi_yesterday, kpi_two_days_ago),
                    'color': 'green' if percent_increase(
                        'ccs_pregnant',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'ccs_pregnant'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Lactating Mothers'),
                    'help_text': _('Total number of lactating women registered'),
                    'percent': percent_increase(
                        'css_lactating_all',
                        kpi_yesterday,
                        kpi_two_days_ago
                    ),
                    'color': 'green' if percent_increase(
                        'css_lactating_all',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'css_lactating_all'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'day'
                },
            ],
            [
                {
                    'label': _('Lactating Women enrolled for ICDS services'),
                    'help_text': _('Total number of lactating women registered and enrolled for ICDS services'),
                    'percent': percent_increase('css_lactating', kpi_yesterday, kpi_two_days_ago),
                    'color': 'green' if percent_increase(
                        'css_lactating',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'css_lactating'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Adolescent Girls (11-18 years)'),
                    'help_text': _('Total number of adolescent girls (11 - 18 years) who are registered'),
                    'percent': percent_increase(
                        'person_adolescent_all',
                        kpi_yesterday,
                        kpi_two_days_ago,
                    ),
                    'color': 'green' if percent_increase(
                        'person_adolescent_all',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'person_adolescent_all'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'day'
                },
            ],
            [
                {
                    'label': _('Adolescent Girls (11-18 years) enrolled for ICDS services'),
                    'help_text': _((
                        "Total number of adolescent girls (11 - 18 years) "
                        "who are registered and enrolled for ICDS services"
                    )),
                    'percent': percent_increase(
                        'person_adolescent',
                        kpi_yesterday,
                        kpi_two_days_ago
                    ),
                    'color': 'green' if percent_increase(
                        'person_adolescent',
                        kpi_yesterday,
                        kpi_two_days_ago) > 0 else 'red',
                    'value': get_value(kpi_yesterday, 'person_adolescent'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Percent Adhaar Seeded Beneficiaries'),
                    'help_text': _(
                        'Percentage of ICDS beneficiaries whose Adhaar identification has been captured'
                    ),
                    'percent': percent_diff(
                        'person_aadhaar',
                        kpi_yesterday,
                        kpi_two_days_ago,
                        'all_persons'
                    ),
                    'value': get_value(kpi_yesterday, 'person_aadhaar'),
                    'all': get_value(kpi_yesterday, 'all_persons'),
                    'format': 'div',
                    'frequency': 'day'
                }
            ]
        ]
    }


def get_awc_report_beneficiary(domain, awc_id, month, two_before):
    data = ChildHealthMonthlyView.objects.filter(
        month__range=(datetime(*two_before), datetime(*month)),
        awc_id=awc_id,
        open_in_month=1,
        valid_in_month=1,
        age_in_months__lte=72
    ).order_by('-month', 'person_name')

    config = {
        'rows': {},
        'months': [
            dt.strftime("%b %Y") for dt in rrule(
                MONTHLY,
                dtstart=datetime(*two_before),
                until=datetime(*month)
            )
        ][::-1],
        'last_month': datetime(*month).strftime("%b %Y"),
    }

    def row_format(row_data):
        return dict(
            nutrition_status=row_data.current_month_nutrition_status,
            recorded_weight=row_data.recorded_weight or 0,
            recorded_height=row_data.recorded_height or 0,
            stunning=row_data.current_month_stunting,
            wasting=row_data.current_month_wasting,
            pse_days_attended=row_data.pse_days_attended
        )

    def base_data(row_data):
        return dict(
            case_id=row_data.case_id,
            person_name=row_data.person_name,
            dob=row_data.dob,
            sex=row_data.sex,
            age=round((datetime(*month).date() - row_data.dob).days / 365.25),
            fully_immunized_date='Yes' if row_data.fully_immunized else 'No',
            mother_name=row_data.mother_name,
            age_in_months=row_data.age_in_months,
        )

    for row in data:
        if row.case_id not in config['rows']:
            config['rows'][row.case_id] = base_data(row)
        config['rows'][row.case_id][row.month.strftime("%b %Y")] = row_format(row)

    return config


def get_beneficiary_details(case_id, month):
    data = ChildHealthMonthlyView.objects.filter(
        case_id=case_id, month__lte=datetime(*month)
    ).order_by('month')

    beneficiary = {
        'weight': [],
        'height': [],
        'wfl': []
    }
    for row in data:
        beneficiary.update({
            'person_name': row.person_name,
            'mother_name': row.mother_name,
            'dob': row.dob,
            'age': round((datetime(*month).date() - row.dob).days / 365.25),
            'sex': row.sex,
            'age_in_months': row.age_in_months,
        })
        beneficiary['weight'].append({'x': int(row.age_in_months), 'y': float(row.recorded_weight or 0)})
        beneficiary['height'].append({'x': int(row.age_in_months), 'y': float(row.recorded_height or 0)})
        beneficiary['wfl'].append({'x': float(row.recorded_height or 0), 'y': float(row.recorded_weight or 0)})
    return beneficiary
