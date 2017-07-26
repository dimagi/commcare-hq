import json
import os
from collections import OrderedDict

from datetime import datetime, timedelta

import operator

from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY
from django.urls.base import reverse

from corehq.util.quickcache import quickcache
from django.db.models.aggregates import Sum, Avg
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import StaticReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from custom.icds_reports.const import LocationTypes
from dimagi.utils.dates import DateSpan, rrule, MONTHLY

from custom.icds_reports.models import AggChildHealthMonthly, AggAwcMonthly, \
    AggCcsRecordMonthly, AggAwcDailyView, DailyAttendanceView, ChildHealthMonthlyView

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": operator.contains,
}

RED = '#d60000'
YELLOW = '#f2ed00'
ORANGE = '#df7400'
BLUE = '#006fdf'
GREEN = '#009811'
GREY = '#9D9D9D'


class MPRData(object):
    resource_file = 'resources/block_mpr.json'


class ASRData(object):
    resource_file = 'resources/block_asr.json'


class ICDSData(object):

    def __init__(self, domain, filters, report_id):
        report_config = ReportFactory.from_spec(
            StaticReportConfiguration.by_id(report_id.format(domain=domain))
        )
        report_config.set_filter_values(filters)
        self.report_config = report_config

    def data(self):
        return self.report_config.get_data()


class ICDSMixin(object):
    has_sections = False
    posttitle = None

    def __init__(self, config):
        self.config = config

    @property
    def subtitle(self):
        return []

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        return [[]]

    @property
    def sources(self):
        with open(os.path.join(os.path.dirname(__file__), self.resource_file)) as f:
            return json.loads(f.read())[self.slug]

    @property
    def selected_location(self):
        if self.config['location_id']:
            return SQLLocation.objects.get(
                location_id=self.config['location_id']
            )

    @property
    def awc(self):
        if self.config['location_id']:
            return self.selected_location.get_descendants(include_self=True).filter(
                location_type__name='awc'
            )

    @property
    def awc_number(self):
        if self.awc:
            return len(
                [
                    loc for loc in self.awc
                    if 'test' not in loc.metadata and loc.metadata.get('test', '').lower() != 'yes'
                ]
            )

    def custom_data(self, selected_location, domain):
        data = {}

        for config in self.sources['data_source']:
            filters = {}
            if selected_location:
                key = selected_location.location_type.name.lower() + '_id'
                filters = {
                    key: [Choice(value=selected_location.location_id, display=selected_location.name)]
                }
            if 'date_filter_field' in config:
                filters.update({config['date_filter_field']: self.config['date_span']})
            if 'filter' in config:
                for fil in config['filter']:
                    if 'type' in fil:
                        now = datetime.now()
                        start_date = now if 'start' not in fil else now - timedelta(days=fil['start'])
                        end_date = now if 'end' not in fil else now - timedelta(days=fil['end'])
                        datespan = DateSpan(start_date, end_date)
                        filters.update({fil['column']: datespan})
                    else:
                        filters.update({
                            fil['column']: {
                                'operator': fil['operator'],
                                'operand': fil['value']
                            }
                        })

            report_data = ICDSData(domain, filters, config['id']).data()
            for column in config['columns']:
                column_agg_func = column['agg_fun']
                column_name = column['column_name']
                column_data = 0
                if column_agg_func == 'sum':
                    column_data = sum([x.get(column_name, 0) for x in report_data])
                elif column_agg_func == 'count':
                    column_data = len(report_data)
                elif column_agg_func == 'count_if':
                    value = column['condition']['value']
                    op = column['condition']['operator']

                    def check_condition(v):
                        if isinstance(v, basestring):
                            fil_v = str(value)
                        elif isinstance(v, int):
                            fil_v = int(value)
                        else:
                            fil_v = value

                        if op == "in":
                            return OPERATORS[op](fil_v, v)
                        else:
                            return OPERATORS[op](v, fil_v)

                    column_data = len([val for val in report_data if check_condition(val[column_name])])
                elif column_agg_func == 'avg':
                    values = [x.get(column_name, 0) for x in report_data]
                    column_data = sum(values) / (len(values) or 1)
                column_display = column_name if 'column_in_report' not in column else column['column_in_report']
                data.update({
                    column_display: data.get(column_display, 0) + column_data
                })
        return data


class ICDSDataTableColumn(DataTablesColumn):

    @property
    def render_html(self):
        column_params = dict(
            title=self.html,
            sort=self.sortable,
            rotate=self.rotate,
            css="span%d" % self.css_span if self.css_span > 0 else '',
            rowspan=self.rowspan,
            help_text=self.help_text,
            expected=self.expected
        )
        return render_to_string("icds_reports/partials/column.html", dict(
            col=column_params
        ))


def percent_increase(prop, data, prev_data):
    current = 0
    previous = 0
    if data:
        current = data[0][prop]
    if prev_data:
        previous = prev_data[0][prop]
    return ((current or 0) - (previous or 0)) / float(previous or 1) * 100


def percent_diff(property, current_data, prev_data, all):
    current = 0
    curr_all = 1
    prev = 0
    prev_all = 1
    if current_data:
        current = (current_data[0][property] or 0)
        curr_all = (current_data[0][all] or 1)

    if prev_data:
        prev = (prev_data[0][property] or 0)
        prev_all = (prev_data[0][all] or 1)

    current_percent = current / float(curr_all) * 100
    prev_percent = prev / float(prev_all) * 100
    return current_percent - prev_percent


def get_value(data, prop):
    return (data[0][prop] or 0) if data else 0


def get_location_filter(location, domain, config):
    loc_level = 'state'
    if location:
        try:
            sql_location = SQLLocation.objects.get(location_id=location, domain=domain)
            locations = sql_location.get_ancestors(include_self=True)
            aggregation_level = locations.count() + 1
            if sql_location.location_type.code != LocationTypes.AWC:
                loc_level = LocationType.objects.filter(
                    parent_type=sql_location.location_type,
                    domain=domain
                )[0].code
            else:
                loc_level = LocationTypes.AWC
            for loc in locations:
                location_key = '%s_id' % loc.location_type.code
                config.update({
                    location_key: loc.location_id,
                })
            config.update({
                'aggregation_level': aggregation_level
            })
        except SQLLocation.DoesNotExist:
            pass
    return loc_level


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


@quickcache(['config'], timeout=24 * 60 * 60)
def get_maternal_child_data(config):

    def get_data_for_child_health_monthly(date, filters):
        return AggChildHealthMonthly.objects.filter(
            month=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            underweight=(
                Sum('nutrition_status_moderately_underweight') + Sum('nutrition_status_severely_underweight')
            ),
            valid=Sum('wer_eligible'),
            wasting=Sum('wasting_moderate') + Sum('wasting_severe'),
            stunting=Sum('stunting_moderate') + Sum('stunting_severe'),
            height_eli=Sum('height_eligible'),
            low_birth_weight=Sum('low_birth_weight_in_month'),
            bf_birth=Sum('bf_at_birth'),
            born=Sum('born_in_month'),
            ebf=Sum('ebf_in_month'),
            ebf_eli=Sum('ebf_eligible'),
            cf_initiation=Sum('cf_initiation_in_month'),
            cf_initiation_eli=Sum('cf_initiation_eligible')
        )

    def get_data_for_deliveries(date, filters):
        return AggCcsRecordMonthly.objects.filter(
            month=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            institutional_delivery=Sum('institutional_delivery_in_month'),
            delivered=Sum('delivered_in_month')
        )

    current_month = datetime(*config['month'])
    previous_month = datetime(*config['prev_month'])
    del config['month']
    del config['prev_month']

    this_month_data = get_data_for_child_health_monthly(current_month, config)
    prev_month_data = get_data_for_child_health_monthly(previous_month, config)

    deliveries_this_month = get_data_for_deliveries(current_month, config)
    deliveries_prev_month = get_data_for_deliveries(previous_month, config)

    return {
        'records': [
            [
                {
                    'label': _('% Underweight Children (weight-for-age)'),
                    'help_text': _((
                        "Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age "
                        "less than -2 standard deviations of the WHO Child Growth Standards median. Children who "
                        "are moderately or severely underweight have a higher risk of mortality."
                    )),
                    'percent': percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid'
                    ),
                    'value': get_value(this_month_data, 'underweight'),
                    'all': get_value(this_month_data, 'valid'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'underweight_children'
                },
                {
                    'label': _('% Wasting (weight-for-height)'),
                    'help_text': _((
                        "Percentage of children (6-60 months) with weight-for-height below -3 standard "
                        "deviations of the WHO Child Growth Standards median. Severe Acute Malnutrition "
                        "(SAM) or wasting in children is a symptom of acute undernutrition usually as a "
                        "consequence of insufficient food intake or a high incidence of infectious "
                        "diseases.")
                    ),
                    'percent': percent_diff(
                        'wasting',
                        this_month_data,
                        prev_month_data,
                        'height_eli'
                    ),
                    'value': get_value(this_month_data, 'wasting'),
                    'all': get_value(this_month_data, 'height_eli'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'wasting'
                }
            ],
            [
                {
                    'label': _('% Stunting (height-for-age)'),
                    'help_text': _((
                        "Percentage of children (6-60 months) with height-for-age below -2Z standard deviations "
                        "of the WHO Child Growth Standards median. Stunting in children is a sign of chronic "
                        "undernutrition and has long lasting harmful consequences on the growth of a child")
                    ),
                    'percent': percent_diff(
                        'stunting',
                        this_month_data,
                        prev_month_data,
                        'height_eli'
                    ),
                    'value': get_value(this_month_data, 'stunting'),
                    'all': get_value(this_month_data, 'height_eli'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': 'stunning'
                },
                {
                    'label': _('% Newborns with Low Birth Weight'),
                    'help_text': _((
                        "Percentage of newborns with born with birth weight less than 2500 grams. Newborns with"
                        " Low Birth Weight are closely associated with foetal and neonatal mortality and "
                        "morbidity, inhibited growth and cognitive development, and chronic diseases later "
                        "in life")),
                    'percent': percent_diff(
                        'low_birth_weight',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'value': get_value(this_month_data, 'low_birth_weight'),
                    'all': get_value(this_month_data, 'born'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': ''
                }
            ],
            [
                {
                    'label': _('% Early Initiation of Breastfeeding'),
                    'help_text': _((
                        "Percentage of children breastfed within an hour of birth. Early initiation of "
                        "breastfeeding ensure the newborn recieves the 'first milk' rich in nutrients "
                        "and encourages exclusive breastfeeding practic")
                    ),
                    'percent': percent_diff(
                        'bf_birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'value': get_value(this_month_data, 'bf_birth'),
                    'all': get_value(this_month_data, 'born'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': ''
                },
                {
                    'label': _('% Exclusive breastfeeding'),
                    'help_text': _((
                        "Percentage of children between 0 - 6 months exclusively breastfed. An infant is "
                        "exclusively breastfed if they recieve only breastmilk with no additional food, "
                        "liquids (even water) ensuring optimal nutrition and growth between 0 - 6 months")
                    ),
                    'percent': percent_diff(
                        'ebf',
                        this_month_data,
                        prev_month_data,
                        'ebf_eli'
                    ),
                    'value': get_value(this_month_data, 'ebf'),
                    'all': get_value(this_month_data, 'ebf_eli'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': ''
                }
            ],
            [
                {
                    'label': _('% Children initiated appropriate complementary feeding'),
                    'help_text': _((
                        "Percentage of children between 6 - 8 months given timely introduction to solid or "
                        "semi-solid food. Timely intiation of complementary feeding in addition to "
                        "breastmilk at 6 months of age is a key feeding practice to reduce malnutrition")
                    ),
                    'percent': percent_diff(
                        'cf_initiation',
                        this_month_data,
                        prev_month_data,
                        'cf_initiation_eli'
                    ),
                    'value': get_value(this_month_data, 'cf_initiation'),
                    'all': get_value(this_month_data, 'cf_initiation_eli'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': ''
                },
                {
                    'label': _('% Institutional deliveries'),
                    'help_text': _((
                        "Percentage of pregant women who delivered in a public or private medical facility "
                        "in the last month. Delivery in medical instituitions is associated with a "
                        "decrease maternal mortality rate")
                    ),
                    'percent': percent_diff(
                        'institutional_delivery',
                        deliveries_this_month,
                        deliveries_prev_month,
                        'delivered'
                    ),
                    'value': get_value(deliveries_this_month, 'institutional_delivery'),
                    'all': get_value(deliveries_this_month, 'delivered'),
                    'format': 'percent_and_div',
                    'frequency': 'month',
                    'redirect': ''
                }
            ]
        ]
    }


def get_cas_reach_data(yesterday, config):
    yesterday_date = datetime(*yesterday)
    two_days_ago = (yesterday_date - relativedelta(days=1)).date()

    def get_data_for_awc_monthly(month, filters):
        return AggAwcMonthly.objects.filter(
            month=month, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            states=Sum('num_launched_states'),
            districts=Sum('num_launched_districts'),
            blocks=Sum('num_launched_blocks'),
            supervisors=Sum('num_launched_supervisors'),
            awcs=Sum('num_launched_awcs'),

        )

    def get_data_for_daily_usage(date, filters):
        return AggAwcDailyView.objects.filter(
            date=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            awcs=Sum('num_awcs'),
            daily_attendance=Sum('daily_attendance_open')
        )

    current_month = datetime(*config['month'])
    previous_month = datetime(*config['prev_month'])
    del config['month']
    del config['prev_month']

    awc_this_month_data = get_data_for_awc_monthly(current_month, config)
    awc_prev_month_data = get_data_for_awc_monthly(previous_month, config)

    daily_yesterday = get_data_for_daily_usage(yesterday_date, config)
    daily_two_days_ago = get_data_for_daily_usage(two_days_ago, config)

    return {
        'records': [
            [
                {
                    'label': _('Number of AWCs Open yesterday'),
                    'help_text': _(("Total Number of Angwanwadi Centers that were open yesterday "
                                    "by the AWW or the AWW helper")),
                    'percent': percent_increase('daily_attendance', daily_yesterday, daily_two_days_ago),
                    'value': get_value(daily_yesterday, 'daily_attendance'),
                    'all': get_value(daily_yesterday, 'awcs'),
                    'format': 'div',
                    'frequency': 'day'
                },
                {
                    'label': _('States/UTs covered'),
                    'help_text': _('Total States that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'states'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month'
                }
            ],
            [
                {
                    'label': _('Blocks covered'),
                    'help_text': _('Total Blocks that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'blocks'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month'
                },
                {
                    'label': _('Districts covered'),
                    'help_text': _('Total Districts that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'districts'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month'
                }
            ],
            [
                {
                    'label': _('Sectors covered'),
                    'help_text': _('Total Sectors that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(awc_this_month_data, 'supervisors'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month'
                },
                {
                    'label': _('AWCs covered'),
                    'help_text': _('Total AWCs that have launched ICDS CAS'),
                    'percent': percent_increase('awcs', awc_this_month_data, awc_prev_month_data),
                    'value': get_value(awc_this_month_data, 'awcs'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'month'
                }
            ]
        ]
    }


def get_demographics_data(yesterday, config):
    yesterday_date = datetime(*yesterday)
    two_days_ago = (yesterday_date - relativedelta(days=1)).date()

    def get_data_for(date, filters):
        return AggAwcDailyView.objects.filter(
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

    yesterday_data = get_data_for(yesterday_date, config)
    two_days_ago_data = get_data_for(two_days_ago, config)

    return {
        'records': [
            [
                {
                    'label': _('Registered Households'),
                    'help_text': _('Total number of households registered'),
                    'percent': percent_increase('household', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'household'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Children (0-6 years)'),
                    'help_text': _('Total number of children registered between the age of 0 - 6 years'),
                    'percent': percent_increase('child_health_all', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'child_health_all'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
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
                    'value': get_value(yesterday_data, 'child_health'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Pregnant Women'),
                    'help_text': _('Total number of pregnant women registered'),
                    'percent': percent_increase('ccs_pregnant_all', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'ccs_pregnant_all'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                }
            ], [
                {
                    'label': _('Pregnant Women enrolled for ICDS services'),
                    'help_text': _('Total number of pregnant women registered and enrolled for ICDS services'),
                    'percent': percent_increase('ccs_pregnant', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'ccs_pregnant'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Lactating Women'),
                    'help_text': _('Total number of lactating women registered'),
                    'percent': percent_increase('css_lactating_all', yesterday_data, two_days_ago_data),
                    'value': get_value(yesterday_data, 'css_lactating_all'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                }
            ], [
                {
                    'label': _('Lactating Women enrolled for ICDS services'),
                    'help_text': _('Total number of lactating women registered and enrolled for ICDS services'),
                    'percent': percent_increase('css_lactating', yesterday_data, two_days_ago_data),
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
                    'value': get_value(yesterday_data, 'person_adolescent_all'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
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
                    'value': get_value(yesterday_data, 'person_adolescent'),
                    'all': None,
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('% Adhaar seeded beneficaries'),
                    'help_text': _((
                        'Percentage of ICDS beneficiaries whose Adhaar identification has been captured'
                    )),
                    'percent': percent_diff(
                        'person_aadhaar',
                        yesterday_data,
                        two_days_ago_data,
                        'all_persons'
                    ),
                    'value': get_value(yesterday_data, 'person_aadhaar'),
                    'all': get_value(yesterday_data, 'all_persons'),
                    'format': 'number',
                    'frequency': 'day'
                }
            ]
        ]
    }


def get_awc_infrastructure_data(config):
    def get_data_for(month, filters):
        return AggAwcMonthly.objects.filter(
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
                    'label': _('% AWCs with Clean Drinking Water'),
                    'help_text': _('Percentage of AWCs with a source of clean drinking water'),
                    'percent': percent_diff(
                        'clean_water',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': get_value(this_month_data, 'clean_water'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _((
                        "% AWCs with Functional Toilet")
                    ),
                    'help_text': _('% AWCs with functional toilet'),
                    'percent': percent_diff(
                        'functional_toilet',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': get_value(this_month_data, 'functional_toilet'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                }
            ],
            [
                {
                    'label': _('% AWCs with Electricity'),
                    'help_text': _('Percentage of AWCs with access to electricity'),
                    'percent': 0,
                    'value': 0,
                    'all': 0,
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('% AWCs with Medicine Kit'),
                    'help_text': _('Percentage of AWCs with a Medicine Kit'),
                    'percent': percent_diff(
                        'medicine_kits',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': get_value(this_month_data, 'medicine_kits'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                }
            ],
            [
                {
                    'label': _('% AWCs with Weighing Scale: Infants'),
                    'help_text': _('Percentage of AWCs with weighing scale for infants'),
                    'percent': percent_diff(
                        'infant_scale',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': get_value(this_month_data, 'infant_scale'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('% AWCs with Weighing Scale: Mother and Child'),
                    'help_text': _('Percentage of AWCs with weighing scale for mother and child'),
                    'percent': percent_diff(
                        'adult_scale',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': get_value(this_month_data, 'adult_scale'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                }
            ],
            [
                {
                    'label': _('Total number of AWCs with an infantometer'),
                    'help_text': _('Percentage of AWCs with an Infantometer'),
                    'percent': 0,
                    'value': 0,
                    'all': 0,
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('Total number of AWCs with a stadiometer'),
                    'help_text': _('Percentage of AWCs with a Stadiometer'),
                    'percent': 0,
                    'value': 0,
                    'all': 0,
                    'format': 'percent_and_div',
                    'frequency': 'month'
                }
            ]
        ]
    }


def get_awc_opened_data(filters):

    def get_data_for(date):
        return AggAwcDailyView.objects.filter(
            date=datetime(*date), aggregation_level=1
        ).values(
            'state_name'
        ).annotate(
            awcs=Sum('awc_count'),
            daily_attendance=Sum('daily_attendance_open'),
        )

    yesterday_data = get_data_for(filters['yesterday'])
    data = {}
    num = 0
    denom = 0
    for row in yesterday_data:
        awcs = row['awcs']
        name = row['state_name']
        daily = row['daily_attendance']
        num += daily
        denom += awcs
        percent = (daily or 0) * 100 / (awcs or 1)
        if 0 <= percent < 51:
            data.update({name: {'fillKey': '0%-50%'}})
        elif 51 <= percent <= 75:
            data.update({name: {'fillKey': '51%-75%'}})
        elif percent > 75:
            data.update({name: {'fillKey': '75%-100%'}})
    return {
        "configs": [
            {
                "slug": "awc_opened",
                "label": "Awc Opened yesterday",
                "fills": {
                    '0%-50%': RED,
                    '51%-75%': YELLOW,
                    '75%-100%': GREEN,
                    'defaultFill': GREY,
                },
                "rightLegend": {
                    "average": num * 100 / (denom or 1),
                    "info": _("Percentage of Angwanwadi Centers that were open yesterday")
                },
                "data": data,
            }
        ]
    }


# @quickcache(['config', 'loc_level'], timeout=24 * 60 * 60)
def get_prevalence_of_undernutrition_data_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            normal=Sum('nutrition_status_normal'),
            valid=Sum('wer_eligible'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['valid']
        name = row['%s_name' % loc_level]

        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']
        normal = row['normal']

        value = ((moderately_underweight or 0) + (severely_underweight or 0)) * 100 / (valid or 1)
        average.append(value)
        row_values = {
            'severely_underweight': severely_underweight or 0,
            'moderately_underweight': moderately_underweight or 0,
            'total': valid or 0,
            'normal': normal
        }
        if value <= 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 21 <= value <= 35:
            row_values.update({'fillKey': '21%-35%'})
        elif value > 35:
            row_values.update({'fillKey': '36%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': GREEN})
    fills.update({'21%-35%': YELLOW})
    fills.update({'36%-100%': RED})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "moderately_underweight",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age "
                    "less than -2 standard deviations of the WHO Child Growth Standards median. "
                    "<br/><br/>"
                    "Children who are moderately or severely underweight have a higher risk of mortality"
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_prevalence_of_undernutrition_data_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        moderately_underweight=Sum('nutrition_status_moderately_underweight'),
        severely_underweight=Sum('nutrition_status_severely_underweight'),
        valid=Sum('valid_in_month'),
    ).order_by('month')

    data = {
        'green': OrderedDict(),
        'orange': OrderedDict(),
        'red': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['green'][miliseconds] = {'y': 0, 'all': 0}
        data['orange'][miliseconds] = {'y': 0, 'all': 0}
        data['red'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        valid = row['valid']
        location = row['%s_name' % loc_level]
        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']

        underweight = ((moderately_underweight or 0) + (severely_underweight or 0)) * 100 / (valid or 1)

        if location in best_worst:
            best_worst[location].append(underweight)
        else:
            best_worst[location] = [underweight]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['orange'][date_in_miliseconds]['y'] += moderately_underweight
        data['orange'][date_in_miliseconds]['all'] += valid
        data['red'][date_in_miliseconds]['y'] += severely_underweight
        data['red'][date_in_miliseconds]['all'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['orange'].iteritems()
                ],
                "key": "% Moderately Underweight (-2 SD)",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['red'].iteritems()
                ],
                "key": "% Severely Underweight (-3 SD) ",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_prevalence_of_undernutrition_sector_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        moderately_underweight=Sum('nutrition_status_moderately_underweight'),
        severely_underweight=Sum('nutrition_status_severely_underweight'),
        valid=Sum('wer_eligible'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        valid = row['valid']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']

        value = ((moderately_underweight or 0) + (severely_underweight or 0)) * 100 / float(valid or 1)

        if value <= 20.0:
            loc_data['green'] += 1
        elif 20.0 <= value <= 35.0:
            loc_data['orange'] += 1
        elif value > 35.0:
            loc_data['red'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-20%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": chart_data['orange'],
                "key": "11%-35%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "36%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ]
    }


def get_awc_reports_system_usage(config, month, prev_month, two_before, loc_level):

    def get_data_for(filters, date):
        return AggAwcMonthly.objects.filter(
            month=datetime(*date), **filters
        ).values(
            loc_level
        ).annotate(
            awc_open=Sum('awc_days_open'),
            weighed=Sum('wer_weighed'),
            all=Sum('wer_eligible'),
        )

    chart_data = DailyAttendanceView.objects.filter(
        pse_date__range=(datetime(*two_before), datetime(*month)), **config
    ).values(
        'pse_date', 'aggregation_level'
    ).annotate(
        awc_count=Sum('awc_open_count'),
        attended_children=Avg('attended_children_percent')
    ).order_by('pse_date')

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


def get_awc_reports_pse(config, month, two_before, domain):

    map_image_data = DailyAttendanceView.objects.filter(
        pse_date__range=(datetime(*two_before), datetime(*month)), **config
    ).values(
        'awc_name', 'form_location_lat', 'form_location_long', 'image_name', 'doc_id', 'pse_date'
    )

    map_data = {}
    image_data = []
    tmp_image = []
    img_count = 0
    count = 1
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
        url = reverse('download_attachment', kwargs={'domain': domain, 'instance_id': doc_id})
        if image_name:
            tmp_image.append({
                'id': count,
                'image': url + '?attachment=' + image_name,
                'date': pse_date.strftime("%d/%m/%Y")
            })
            img_count += 1
            count += 1
            if img_count == 4:
                img_count = 0
                image_data.append(tmp_image)
                tmp_image = []
    if tmp_image:
        image_data.append(tmp_image)

    return {
        'map': {
            'markers': map_data,
        },
        'images': image_data
    }


def get_awc_reports_maternal_child(config, month, prev_month):

    def get_data_for(date):
        return AggChildHealthMonthly.objects.filter(
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

    this_month_data = get_data_for(datetime(*month))
    prev_month_data = get_data_for(datetime(*prev_month))

    return {
        'kpi': [
            [
                {
                    'label': _('Prevalence of undernutrition (weight-for-age)'),
                    'help_text': _((
                        "Percentage of children with weight-for-age less than -2 standard deviations of the "
                        "WHO Child Growth Standards median. Children who are moderately or severely underweight "
                        "have a higher risk of mortality."
                    )),
                    'percent': percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid_in_month'
                    ),
                    'value': get_value(this_month_data, 'underweight'),
                    'all': get_value(this_month_data, 'valid_in_month'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('% Immunization coverage (at age 1 year)'),
                    'help_text': _((
                        "Percentage of children 1 year+ who have recieved complete immunization as per "
                        "National Immunization Schedule of India required by age 1"
                    )),
                    'percent': percent_diff(
                        'immunized',
                        this_month_data,
                        prev_month_data,
                        'eligible'
                    ),
                    'value': get_value(this_month_data, 'immunized'),
                    'all': get_value(this_month_data, 'eligible'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ],
            [
                {
                    'label': _('% Wasting (weight-for-height)'),
                    'help_text': _((
                        "Percentage of children (6-60 months) with weight-for-height below -3 standard "
                        "deviations of the WHO Child Growth Standards median. Severe Acute Malnutrition "
                        "(SAM) or wasting in children is a symptom of acute undernutrition usually "
                        "as a consequence"
                    )),
                    'percent': percent_diff(
                        'wasting',
                        this_month_data,
                        prev_month_data,
                        'height'
                    ),
                    'value': get_value(this_month_data, 'wasting'),
                    'all': get_value(this_month_data, 'height'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('% Stunting (height-for-age)'),
                    'help_text': _((
                        "Percentage of children (6-60 months) with height-for-age below -2Z standard "
                        "deviations of the WHO Child Growth Standards median. Stunting in children is a "
                        "sign of chronic undernutrition and has long lasting harmful consequences on the "
                        "growth of a child"
                    )),
                    'percent': percent_diff(
                        'stunting',
                        this_month_data,
                        prev_month_data,
                        'height'
                    ),
                    'value': get_value(this_month_data, 'stunting'),
                    'all': get_value(this_month_data, 'height'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ],
            [
                {
                    'label': _('% Newborns with Low Birth Weight'),
                    'help_text': None,
                    'percent': percent_diff(
                        'low_birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'value': get_value(this_month_data, 'low_birth'),
                    'all': get_value(this_month_data, 'born'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('% Early Initiation of Breastfeeding'),
                    'help_text': None,
                    'percent': percent_diff(
                        'birth',
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'value': get_value(this_month_data, 'birth'),
                    'all': get_value(this_month_data, 'born'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ],
            [
                {
                    'label': _('% Exclusive breastfeeding'),
                    'help_text': None,
                    'percent': percent_diff(
                        'month_ebf',
                        this_month_data,
                        prev_month_data,
                        'ebf'
                    ),
                    'value': get_value(this_month_data, 'month_ebf'),
                    'all': get_value(this_month_data, 'ebf'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
                {
                    'label': _('% Children initiated appropriate complementary feeding'),
                    'help_text': None,
                    'percent': percent_diff(
                        'month_cf',
                        this_month_data,
                        prev_month_data,
                        'cf'
                    ),
                    'value': get_value(this_month_data, 'month_cf'),
                    'all': get_value(this_month_data, 'cf'),
                    'format': 'percent_and_div',
                    'frequency': 'month'
                },
            ]
        ]
    }


def get_awc_report_demographics(config, month):
    selected_month = datetime(*month)

    def get_data_for(date, filters):
        return AggAwcMonthly.objects.filter(
            month=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            household=Sum('cases_household')
        )

    chart = AggChildHealthMonthly.objects.filter(
        month=selected_month, **config
    ).values(
        'age_tranche', 'aggregation_level'
    ).annotate(
        valid=Sum('valid_in_month')
    ).order_by('age_tranche')

    chart_data = {
        '0-1 month': 0,
        '1-6 months': 0,
        '6-12 months': 0,
        '1-3 years': 0,
        '3-6 years': 0
    }
    for chart_row in chart:
        if chart_row['age_tranche']:
            age = int(chart_row['age_tranche'])
            valid = chart_row['valid']
            if 0 <= age < 1:
                chart_data['0-1 month'] += valid
            elif 1 <= age < 6:
                chart_data['1-6 months'] += valid
            elif 6 <= age < 12:
                chart_data['6-12 months'] += valid
            elif 12 <= age < 36:
                chart_data['1-3 years'] += valid
            elif 36 <= age <= 72:
                chart_data['3-6 years'] += valid

    def get_data_for_kpi(filters, date):
        return AggAwcDailyView.objects.filter(
            date=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            ccs_pregnant=Sum('cases_ccs_pregnant'),
            ccs_lactating=Sum('cases_ccs_lactating'),
            adolescent=Sum('cases_person_adolescent_girls_11_18'),
            has_aadhaar=Sum('cases_person_has_aadhaar'),
            all_cases=Sum('cases_person')
        )

    yesterday = datetime.now() - relativedelta(days=1)
    two_days_ago = yesterday - relativedelta(days=1)
    kpi_yesterday = get_data_for_kpi(config, yesterday.date())
    kpi_two_days_ago = get_data_for_kpi(config, two_days_ago.date())

    this_month = get_data_for(selected_month, config)
    prev_month = get_data_for(selected_month - relativedelta(months=1), config)

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
                        this_month,
                        prev_month,
                    ),
                    'value': get_value(this_month, 'household'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'month'
                }
            ],
            [
                {
                    'label': _('Pregnant Women'),
                    'help_text': _("Total number of pregnant women registered"),
                    'percent': percent_increase(
                        'ccs_pregnant',
                        kpi_yesterday,
                        kpi_two_days_ago,
                    ),
                    'value': get_value(kpi_yesterday, 'ccs_pregnant'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('Lactating Mothers'),
                    'help_text': _('Total number of lactating women registered'),
                    'percent': percent_increase(
                        ['ccs_lactating'],
                        kpi_yesterday,
                        kpi_two_days_ago
                    ),
                    'value': get_value(kpi_yesterday, 'ccs_lactating'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'day'
                }
            ],
            [
                {
                    'label': _('Adolescent Girls (11-18 years)'),
                    'help_text': _('Total number of adolescent girls who are registered'),
                    'percent': percent_increase(
                        'adolescent',
                        kpi_yesterday,
                        kpi_two_days_ago,
                    ),
                    'value': get_value(kpi_yesterday, 'adolescent'),
                    'all': '',
                    'format': 'number',
                    'frequency': 'day'
                },
                {
                    'label': _('% Adhaar seeded beneficaries'),
                    'help_text': _(
                        'Percentage of ICDS beneficiaries whose Adhaar identification has been captured'
                    ),
                    'percent': percent_diff(
                        ['has_aadhaar'],
                        kpi_yesterday,
                        kpi_two_days_ago,
                        'all_cases'
                    ),
                    'value': get_value(kpi_yesterday, 'has_aadhaar'),
                    'all': get_value(kpi_yesterday, 'all_cases'),
                    'format': 'div',
                    'frequency': 'day'
                }
            ]
        ]
    }


def get_awc_report_beneficiary(awc_id, month, two_before):
    data = ChildHealthMonthlyView.objects.filter(
        month__range=(datetime(*two_before), datetime(*month)),
        awc_id=awc_id,
        open_in_month=1,
        valid_in_month=1,
        age_in_months__lte=72
    ).order_by('month', 'person_name')

    config = {
        'rows': {},
        'months': [
            dt.strftime("%b %Y") for dt in rrule(
                MONTHLY,
                dtstart=datetime(*two_before),
                until=datetime(*month)
            )
        ],
        'last_month': datetime(*month).strftime("%b %Y")
    }

    def row_format(row_data):
        return dict(
            case_id=row_data.case_id,
            person_name=row_data.person_name,
            dob=row_data.dob,
            sex=row_data.sex,
            age=round((datetime(*month).date() - row_data.dob).days / 365.25),
            fully_immunized_date='Yes' if row_data.fully_immunized_date != '' else 'No',
            nutrition_status=row_data.current_month_nutrition_status,
            recorded_weight=row_data.recorded_weight or 0,
            recorder_height=row_data.recorded_height or 0,
            stunning=row_data.current_month_stunting,
            wasting=row_data.current_month_wasting,
            mother_name=row_data.mother_name,
            pse_days_attended=row_data.pse_days_attended,
            age_in_months=row_data.age_in_months,
        )

    for row in data:
        if row.case_id not in config['rows']:
            config['rows'][row.case_id] = {}
        config['rows'][row.case_id][row.month.strftime("%b %Y")] = row_format(row)

    return config


def get_beneficiary_details(case_id, month):
    data = ChildHealthMonthlyView.objects.filter(
        case_id=case_id, month__lte=datetime(*month)
    ).order_by('month')
    beneficiary = {
        'weight': [],
        'height': [],
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
        beneficiary['weight'].append({'x': row.age_in_months, 'y': (row.recorded_weight or 0)})
        beneficiary['height'].append({'x': row.age_in_months, 'y': (row.recorded_height or 0)})
    return beneficiary


def get_prevalence_of_severe_data_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            moderate=Sum('wasting_moderate'),
            severe=Sum('wasting_severe'),
            normal=Sum('wasting_normal'),
            valid=Sum('height_eligible'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['valid']
        name = row['%s_name' % loc_level]

        severe = row['severe']
        moderate = row['moderate']
        normal = row['normal']

        value = ((moderate or 0) + (severe or 0)) * 100 / (valid or 1)
        average.append(value)
        row_values = {
            'severe': severe or 0,
            'moderate': moderate or 0,
            'total': valid or 0,
            'normal': normal
        }
        if value < 5:
            row_values.update({'fillKey': '0%-5%'})
        elif 5 <= value < 7:
            row_values.update({'fillKey': '5%-7%'})
        elif value >= 7:
            row_values.update({'fillKey': '7%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-5%': GREEN})
    fills.update({'5%-7%': YELLOW})
    fills.update({'7%-100%': RED})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "severe",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of children between 6 - 60 months enrolled for ICDS services with "
                    "weight-for-height below -3 standard deviations of the WHO Child Growth Standards median."
                    "<br/><br/>"
                    "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute "
                    "undernutrition usually as a consequence of insufficient food intake or a high "
                    "incidence of infectious diseases."
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_prevalence_of_severe_data_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        moderate=Sum('wasting_moderate'),
        severe=Sum('wasting_severe'),
        valid=Sum('height_eligible'),
    ).order_by('month')

    data = {
        'red': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['red'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        valid = row['valid']
        location = row['%s_name' % loc_level]
        severe = row['severe']
        moderate = row['moderate']

        underweight = (moderate or 0) + (severe or 0)

        if location in best_worst:
            best_worst[location].append(underweight / float(valid or 1))
        else:
            best_worst[location] = [underweight / float(valid or 1)]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['red'][date_in_miliseconds]['y'] += underweight
        data['red'][date_in_miliseconds]['all'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['red'].iteritems()
                ],
                "key": "Severe and Moderate Acute Malnutrition (SAM and MAM)",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_prevalence_of_severe_sector_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        moderate=Sum('wasting_moderate'),
        severe=Sum('wasting_severe'),
        valid=Sum('height_eligible'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        valid = row['valid']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        severe = row['severe']
        moderate = row['moderate']

        value = ((moderate or 0) + (severe or 0)) * 100 / float(valid or 1)

        if value < 5.0:
            loc_data['green'] += 1
        elif 5.0 <= value < 7.0:
            loc_data['orange'] += 1
        elif value >= 7.0:
            loc_data['red'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-5%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": chart_data['orange'],
                "key": "5%-7%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "7%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ]
    }


def get_prevalence_of_stunning_data_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            moderate=Sum('stunting_moderate'),
            severe=Sum('stunting_severe'),
            normal=Sum('stunting_normal'),
            valid=Sum('height_eligible'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['valid']
        name = row['%s_name' % loc_level]

        severe = row['severe']
        moderate = row['moderate']
        normal = row['normal']

        value = ((moderate or 0) + (severe or 0)) * 100 / (valid or 1)
        average.append(value)
        row_values = {
            'severe': severe or 0,
            'moderate': moderate or 0,
            'total': valid or 0,
            'normal': normal
        }
        if value < 5:
            row_values.update({'fillKey': '0%-25%'})
        elif 5 <= value < 7:
            row_values.update({'fillKey': '25%-38%'})
        elif value >= 7:
            row_values.update({'fillKey': '38%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-25%': GREEN})
    fills.update({'25%-38%': YELLOW})
    fills.update({'38%-100%': RED})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "severe",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of children between 6 - 60 months enrolled for ICDS services with "
                    "weight-for-height below -3 standard deviations of the WHO Child Growth Standards median."
                    "<br/><br/>"
                    "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute "
                    "undernutrition usually as a consequence of insufficient food intake or a high "
                    "incidence of infectious diseases."
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_prevalence_of_stunning_data_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        moderate=Sum('stunting_moderate'),
        severe=Sum('stunting_severe'),
        valid=Sum('height_eligible'),
    ).order_by('month')

    data = {
        'red': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['red'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        valid = row['valid']
        location = row['%s_name' % loc_level]
        severe = row['severe']
        moderate = row['moderate']

        underweight = (moderate or 0) + (severe or 0)

        if location in best_worst:
            best_worst[location].append(underweight / (valid or 1))
        else:
            best_worst[location] = [underweight / (valid or 1)]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['red'][date_in_miliseconds]['y'] += underweight
        data['red'][date_in_miliseconds]['all'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['red'].iteritems()
                ],
                "key": "Moderate or severely stunted growth",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_prevalence_of_stunning_sector_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        moderate=Sum('stunting_moderate'),
        severe=Sum('stunting_severe'),
        valid=Sum('height_eligible'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        valid = row['valid']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        severe = row['severe']
        moderate = row['moderate']

        value = ((moderate or 0) + (severe or 0)) * 100 / float(valid or 1)

        if value < 25.0:
            loc_data['green'] += 1
        elif 25.0 <= value < 38.0:
            loc_data['orange'] += 1
        elif value >= 38.0:
            loc_data['red'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-25%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": chart_data['orange'],
                "key": "25%-38%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "38%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ]
    }


def get_newborn_with_low_birth_weight_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            low_birth=Sum('low_birth_weight_in_month'),
            in_month=Sum('born_in_month'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        name = row['%s_name' % loc_level]

        low_birth = row['low_birth']
        in_month = row['in_month']

        value = (low_birth or 0) * 100 / (in_month or 1)
        average.append(value)
        row_values = {
            'low_birth': low_birth,
            'in_month': in_month,
        }
        if value <= 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 < value < 60:
            row_values.update({'fillKey': '20%-60%'})
        elif value >= 60:
            row_values.update({'fillKey': '60%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': GREEN})
    fills.update({'20%-60%': YELLOW})
    fills.update({'60%-100%': RED})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "low_birth",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of newborns with born with birth weight less than 2500 grams."
                    "<br/><br/>"
                    "Newborns with Low Birth Weight are closely associated with foetal and neonatal "
                    "mortality and morbidity, inhibited growth and cognitive development, and chronic "
                    "diseases later in life"
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_newborn_with_low_birth_weight_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        low_birth=Sum('low_birth_weight_in_month'),
        in_month=Sum('born_in_month'),
    ).order_by('month')

    data = {
        'blue': OrderedDict(),
        'red': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}
        data['red'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        low_birth = row['low_birth']

        value = (low_birth or 0) * 100 / (in_month or 1)

        if location in best_worst:
            best_worst[location].append(value)
        else:
            best_worst[location] = [value]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['blue'][date_in_miliseconds]['y'] += in_month
        data['red'][date_in_miliseconds]['y'] += low_birth

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(val) / len(val)) for key, val in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': val['y'],
                        'all': val['all']
                    } for key, val in data['blue'].iteritems()
                ],
                "key": "Total newborns",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': val['y'],
                        'all': val['all']
                    } for key, val in data['red'].iteritems()
                ],
                "key": "Low birth weight newborns",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_newborn_with_low_birth_weight_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        low_birth=Sum('low_birth_weight_in_month'),
        in_month=Sum('born_in_month'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        in_month = row['in_month']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }

        low_birth = row['low_birth']

        value = (low_birth or 0) * 100 / float(in_month or 1)

        if value <= 20.0:
            loc_data['green'] += 1
        elif 20.0 <= value <= 60.0:
            loc_data['orange'] += 1
        elif value > 60.0:
            loc_data['red'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-20%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": chart_data['orange'],
                "key": "20%-60%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "60%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ]
    }


def get_early_initiation_breastfeeding_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            birth=Sum('bf_at_birth'),
            in_month=Sum('born_in_month'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        name = row['%s_name' % loc_level]

        birth = row['birth']
        in_month = row['in_month']

        value = (birth or 0) * 100 / (in_month or 1)
        average.append(value)
        row_values = {
            'birth': birth,
            'in_month': in_month,
        }
        if value <= 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 < value < 60:
            row_values.update({'fillKey': '20%-60%'})
        elif value >= 60:
            row_values.update({'fillKey': '60%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'60%-100%': GREEN})
    fills.update({'20%-60%': YELLOW})
    fills.update({'0%-20%': RED})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "early_initiation",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of children who were put to the breast within one hour of birth."
                    "<br/><br/>"
                    "Early initiation of breastfeeding ensure the newborn recieves the 'first milk' rich in "
                    "nutrients and encourages exclusive breastfeeding practic"
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_early_initiation_breastfeeding_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        birth=Sum('bf_at_birth'),
        in_month=Sum('born_in_month'),
    ).order_by('month')

    data = {
        'green': OrderedDict(),
        'blue': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['green'][miliseconds] = {'y': 0, 'all': 0}
        data['blue'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]

        birth = row['birth']

        value = (birth or 0) * 100 / (in_month or 1)

        if location in best_worst:
            best_worst[location].append(value)
        else:
            best_worst[location] = [value]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['green'][date_in_miliseconds]['y'] += birth
        data['blue'][date_in_miliseconds]['y'] += in_month

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(val) / len(val)) for key, val in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': val['y'],
                        'all': val['all']
                    } for key, val in data['green'].iteritems()
                ],
                "key": "Children breastfed within one hour of birth",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': val['y'],
                        'all': val['all']
                    } for key, val in data['blue'].iteritems()
                ],
                "key": "Total births",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_early_initiation_breastfeeding_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        birth=Sum('bf_at_birth'),
        in_month=Sum('born_in_month'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        in_month = row['in_month']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }

        birth = row['birth']

        value = (birth or 0) * 100 / float(in_month or 1)

        if value >= 60.0:
            loc_data['green'] += 1
        elif 20.0 <= value < 60.0:
            loc_data['orange'] += 1
        elif value < 20.0:
            loc_data['red'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "60%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": chart_data['orange'],
                "key": "20%-60%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "0%-20%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            }
        ]
    }


def get_exclusive_breastfeeding_data_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            in_month=Sum('ebf_in_month'),
            eligible=Sum('ebf_eligible'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        in_month = row['in_month']

        value = (in_month or 0) * 100 / (valid or 1)
        average.append(value)
        row_values = {
            'children': in_month or 0,
            'all': valid or 0
        }
        if value < 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 <= value < 60:
            row_values.update({'fillKey': '20%-60%'})
        elif value >= 60:
            row_values.update({'fillKey': '60%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': RED})
    fills.update({'20%-60%': YELLOW})
    fills.update({'60%-100%': GREEN})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "severe",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of infants 0-6 months of age who are fed exclusively with breast milk. "
                    "<br/><br/>"
                    "An infant is exclusively breastfed if they recieve only breastmilk with no additional food, "
                    "liquids (even water) ensuring optimal nutrition and growth between 0 - 6 months"
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_exclusive_breastfeeding_data_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        in_month=Sum('ebf_in_month'),
        eligible=Sum('ebf_eligible'),
    ).order_by('month')

    data = {
        'blue': OrderedDict(),
        'green': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}
        data['green'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        valid = row['eligible']

        if location in best_worst:
            best_worst[location].append(in_month / (valid or 1))
        else:
            best_worst[location] = [in_month / (valid or 1)]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['green'][date_in_miliseconds]['y'] += in_month
        data['blue'][date_in_miliseconds]['y'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['green'].iteritems()
                ],
                "key": "Total children exclusively breastfed",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['blue'].iteritems()
                ],
                "key": "Total children 0-6 months",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_exclusive_breastfeeding_sector_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_month=Sum('ebf_in_month'),
        eligible=Sum('ebf_eligible'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        in_month = row['in_month']

        value = (in_month or 0) * 100 / float(valid or 1)

        if value < 20.0:
            loc_data['red'] += 1
        elif 20.0 <= value < 60.0:
            loc_data['orange'] += 1
        elif value >= 60.0:
            loc_data['green'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-20%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            },
            {
                "values": chart_data['orange'],
                "key": "20%-60%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "60%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            }
        ]
    }


def get_children_initiated_data_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            in_month=Sum('cf_initiation_in_month'),
            eligible=Sum('cf_initiation_eligible'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        in_month = row['in_month']

        value = (in_month or 0) * 100 / (valid or 1)
        average.append(value)
        row_values = {
            'children': in_month or 0,
            'all': valid or 0
        }
        if value < 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 <= value < 60:
            row_values.update({'fillKey': '20%-60%'})
        elif value >= 60:
            row_values.update({'fillKey': '60%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': RED})
    fills.update({'20%-60%': YELLOW})
    fills.update({'60%-100%': GREEN})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "severe",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of children between 6 - 8 months given timely introduction to solid, "
                    "semi-solid or soft food."
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_children_initiated_data_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        in_month=Sum('cf_initiation_in_month'),
        eligible=Sum('cf_initiation_eligible'),
    ).order_by('month')

    data = {
        'blue': OrderedDict(),
        'green': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}
        data['green'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        valid = row['eligible']

        if location in best_worst:
            best_worst[location].append(in_month / (valid or 1))
        else:
            best_worst[location] = [in_month / (valid or 1)]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['green'][date_in_miliseconds]['y'] += in_month
        data['blue'][date_in_miliseconds]['y'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['green'].iteritems()
                ],
                "key": "Children began complementary feeding",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['blue'].iteritems()
                ],
                "key": "Total children 6-8 months",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_children_initiated_sector_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_month=Sum('cf_initiation_in_month'),
        eligible=Sum('cf_initiation_eligible'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        in_month = row['in_month']

        value = (in_month or 0) * 100 / float(valid or 1)

        if value < 20.0:
            loc_data['red'] += 1
        elif 20.0 <= value < 60.0:
            loc_data['orange'] += 1
        elif value >= 60.0:
            loc_data['green'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-20%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            },
            {
                "values": chart_data['orange'],
                "key": "20%-60%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "60%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            }
        ]
    }


def get_institutional_deliveries_data_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggCcsRecordMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            in_month=Sum('institutional_delivery_in_month'),
            eligible=Sum('delivered_in_month'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        in_month = row['in_month']

        value = (in_month or 0) * 100 / (valid or 1)
        average.append(value)
        row_values = {
            'children': in_month or 0,
            'all': valid or 0
        }
        if value < 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 <= value < 60:
            row_values.update({'fillKey': '20%-60%'})
        elif value >= 60:
            row_values.update({'fillKey': '60%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': RED})
    fills.update({'20%-60%': YELLOW})
    fills.update({'60%-100%': GREEN})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "institutional_deliveries",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of pregant women who delivered in a public or private medical facility "
                    "in the last month. "
                    "<br/><br/>"
                    "Delivery in medical instituitions is associated with a decrease maternal mortality rate"
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_institutional_deliveries_data_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggCcsRecordMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        in_month=Sum('institutional_delivery_in_month'),
        eligible=Sum('delivered_in_month'),
    ).order_by('month')

    data = {
        'blue': OrderedDict(),
        'green': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}
        data['green'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        valid = row['eligible']

        if location in best_worst:
            best_worst[location].append(in_month / (valid or 1))
        else:
            best_worst[location] = [in_month / (valid or 1)]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['green'][date_in_miliseconds]['y'] += in_month
        data['blue'][date_in_miliseconds]['y'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['green'].iteritems()
                ],
                "key": "Deliveries in public/private medical facility",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['blue'].iteritems()
                ],
                "key": "Total deliveries",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_institutional_deliveries_sector_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggCcsRecordMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_month=Sum('institutional_delivery_in_month'),
        eligible=Sum('delivered_in_month'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        in_month = row['in_month']

        value = (in_month or 0) * 100 / float(valid or 1)

        if value < 20.0:
            loc_data['red'] += 1
        elif 20.0 <= value < 60.0:
            loc_data['orange'] += 1
        elif value >= 60.0:
            loc_data['green'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-20%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            },
            {
                "values": chart_data['orange'],
                "key": "20%-60%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "60%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            }
        ]
    }


def get_immunization_coverage_data_map(config, loc_level):

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            in_month=Sum('fully_immunized_on_time') + Sum('fully_immunized_late'),
            eligible=Sum('fully_immunized_eligible'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        in_month = row['in_month']

        value = (in_month or 0) * 100 / (valid or 1)
        average.append(value)
        row_values = {
            'children': in_month or 0,
            'all': valid or 0
        }
        if value < 20:
            row_values.update({'fillKey': '0%-20%'})
        elif 20 <= value < 60:
            row_values.update({'fillKey': '20%-60%'})
        elif value >= 60:
            row_values.update({'fillKey': '60%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-20%': RED})
    fills.update({'20%-60%': YELLOW})
    fills.update({'60%-100%': GREEN})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "institutional_deliveries",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of children 1 year+ who have recieved complete immunization as per National "
                    "Immunization Schedule of India required by age 1."
                )),
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_immunization_coverage_data_chart(config, loc_level):
    month = datetime(*config['month'])
    three_before = datetime(*config['month']) - relativedelta(months=3)

    config['month__range'] = (three_before, month)
    del config['month']

    chart_data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        'month', '%s_name' % loc_level
    ).annotate(
        in_month=Sum('fully_immunized_on_time') + Sum('fully_immunized_late'),
        eligible=Sum('fully_immunized_eligible'),
    ).order_by('month')

    data = {
        'blue': OrderedDict(),
        'green': OrderedDict()
    }

    dates = [dt for dt in rrule(MONTHLY, dtstart=three_before, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}
        data['green'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['month']
        in_month = row['in_month']
        location = row['%s_name' % loc_level]
        valid = row['eligible']

        if location in best_worst:
            best_worst[location].append(in_month / (valid or 1))
        else:
            best_worst[location] = [in_month / (valid or 1)]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['green'][date_in_miliseconds]['y'] += in_month
        data['blue'][date_in_miliseconds]['y'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['green'].iteritems()
                ],
                "key": "Children received complete immunizations by 1 year",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['blue'].iteritems()
                ],
                "key": "Total ICDS child beneficiaries >1 year",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_immunization_coverage_sector_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['month'] = datetime(*config['month'])
    data = AggChildHealthMonthly.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_month=Sum('fully_immunized_on_time') + Sum('fully_immunized_late'),
        eligible=Sum('fully_immunized_eligible'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        valid = row['eligible']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        in_month = row['in_month']

        value = (in_month or 0) * 100 / float(valid or 1)

        if value < 20.0:
            loc_data['red'] += 1
        elif 20.0 <= value < 60.0:
            loc_data['orange'] += 1
        elif value >= 60.0:
            loc_data['green'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-20%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            },
            {
                "values": chart_data['orange'],
                "key": "20%-60%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "60%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            }
        ]
    }


def get_awc_daily_status_data_map(config, loc_level):

    def get_data_for(filters):
        filters['date'] = datetime(*filters['month'])
        del filters['month']
        return AggAwcDailyView.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            in_day=Sum('daily_attendance_open'),
            all=Sum('num_launched_awcs'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['all']
        name = row['%s_name' % loc_level]

        in_day = row['in_day']

        value = (in_day or 0) * 100 / (valid or 1)
        average.append(value)
        row_values = {
            'in_day': in_day or 0,
            'all': valid or 0
        }
        if value < 50:
            row_values.update({'fillKey': '0%-50%'})
        elif 50 <= value < 75:
            row_values.update({'fillKey': '50%-75%'})
        elif value >= 75:
            row_values.update({'fillKey': '75%-100%'})

        map_data.update({name: row_values})

    fills = OrderedDict()
    fills.update({'0%-50%': RED})
    fills.update({'50%-75%': YELLOW})
    fills.update({'75%-100%': GREEN})
    fills.update({'defaultFill': GREY})

    return [
        {
            "slug": "awc_daily_statuses",
            "label": "",
            "fills": fills,
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of Angwanwadi Centers that were open yesterday."
                )),
                'period': 'Daily',
                "last_modify": datetime.utcnow().strftime("%d/%m/%Y"),
            },
            "data": map_data,
        }
    ]


def get_awc_daily_status_data_chart(config, loc_level):
    month = datetime(*config['month'])
    last = datetime(*config['month']) - relativedelta(days=30)

    config['date__range'] = (last, month)
    del config['month']

    chart_data = AggAwcDailyView.objects.filter(
        **config
    ).values(
        'date', '%s_name' % loc_level
    ).annotate(
        in_day=Sum('daily_attendance_open'),
        all=Sum('num_launched_awcs'),
    ).order_by('date')

    data = {
        'blue': OrderedDict(),
        'green': OrderedDict()
    }

    dates = [dt for dt in rrule(DAILY, dtstart=last, until=month)]

    for date in dates:
        miliseconds = int(date.strftime("%s")) * 1000
        data['blue'][miliseconds] = {'y': 0, 'all': 0}
        data['green'][miliseconds] = {'y': 0, 'all': 0}

    best_worst = {}
    for row in chart_data:
        date = row['date']
        in_day = row['in_day']
        location = row['%s_name' % loc_level]
        valid = row['all']

        if location in best_worst:
            best_worst[location].append(in_day / (valid or 1))
        else:
            best_worst[location] = [in_day / (valid or 1)]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        data['green'][date_in_miliseconds]['y'] += in_day
        data['blue'][date_in_miliseconds]['y'] += valid

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['green'].iteritems()
                ],
                "key": "Number of AWCs launched",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            },
            {
                "values": [
                    {
                        'x': key,
                        'y': value['y'] / float(value['all'] or 1),
                        'all': value['all']
                    } for key, value in data['blue'].iteritems()
                ],
                "key": "Total AWCs open yesterday",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": BLUE
            }
        ],
        "all_locations": top_locations,
        "top_three": top_locations[0:5],
        "bottom_three": top_locations[-6:-1],
        "location_type": loc_level.title() if loc_level != LocationTypes.SUPERVISOR else 'State'
    }


def get_awc_daily_status_sector_data(config, loc_level):
    group_by = ['%s_name' % loc_level]
    if loc_level == LocationTypes.SUPERVISOR:
        config['aggregation_level'] += 1
        group_by.append('%s_name' % LocationTypes.AWC)

    config['date'] = datetime(*config['month'])
    del config['month']
    data = AggAwcDailyView.objects.filter(
        **config
    ).values(
        *group_by
    ).annotate(
        in_day=Sum('daily_attendance_open'),
        all=Sum('num_launched_awcs'),
    ).order_by('%s_name' % loc_level)

    loc_data = {
        'green': 0,
        'orange': 0,
        'red': 0
    }
    tmp_name = ''
    rows_for_location = 0

    chart_data = {
        'green': [],
        'orange': [],
        'red': []
    }

    for row in data:
        valid = row['all']
        name = row['%s_name' % loc_level]

        if tmp_name and name != tmp_name:
            chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
            chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
            chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])
            rows_for_location = 0
            loc_data = {
                'green': 0,
                'orange': 0,
                'red': 0
            }
        in_day = row['in_day']

        value = (in_day or 0) * 100 / float(valid or 1)

        if value < 50.0:
            loc_data['red'] += 1
        elif 50.0 <= value < 75.0:
            loc_data['orange'] += 1
        elif value >= 75.0:
            loc_data['green'] += 1

        tmp_name = name
        rows_for_location += 1

    chart_data['green'].append([tmp_name, (loc_data['green'] / float(rows_for_location or 1))])
    chart_data['orange'].append([tmp_name, (loc_data['orange'] / float(rows_for_location or 1))])
    chart_data['red'].append([tmp_name, (loc_data['red'] / float(rows_for_location or 1))])

    return {
        "chart_data": [
            {
                "values": chart_data['green'],
                "key": "0%-50%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": RED
            },
            {
                "values": chart_data['orange'],
                "key": "50%-75%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": ORANGE
            },
            {
                "values": chart_data['red'],
                "key": "75%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": GREEN
            }
        ]
    }