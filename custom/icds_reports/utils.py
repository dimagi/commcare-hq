import json
import os

from datetime import datetime, timedelta

import operator

from dateutil.relativedelta import relativedelta

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
from dimagi.utils.dates import DateSpan

from custom.icds_reports.models import AggDailyUsageView, AggChildHealthMonthly, AggAwcMonthly, \
    AggCcsRecordMonthly, AggAwcDailyView, DailyAttendanceView

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": operator.contains,
}


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


def get_location_filter(request, domain, config):
    location = request.GET.get('location', None)
    loc_level = 'state'
    if location:
        try:
            domain = domain
            sql_location = SQLLocation.objects.get(location_id=location, domain=domain)
            aggregation_level = sql_location.get_ancestors(include_self=True).count() + 1
            location_code = sql_location.site_code
            if sql_location.location_type.code != LocationTypes.AWC:
                loc_level = LocationType.objects.filter(
                    parent_type=sql_location.location_type,
                    domain=domain
                )[0].code
            else:
                loc_level = LocationTypes.AWC
            location_key = '%s_site_code' % sql_location.location_type.code
            config.update({
                location_key: location_code,
                'aggregation_level': aggregation_level
            })
        except SQLLocation.DoesNotExist:
            pass
    return loc_level


def get_system_usage_data(yesterday, before_yesterday, config):

    def get_data_for(date, filters):
        return AggDailyUsageView.objects.filter(
            date=datetime(*date), **filters
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

    yesterday_data = get_data_for(yesterday, config)
    before_yesterday_data = get_data_for(before_yesterday, config)

    return {
        'records': [
            [
                {
                    'label': _('Number of AWCs Open yesterday'),
                    'help_text': _(("Total Number of Angwanwadi Centers that were open yesterday "
                                    "by the AWW or the AWW helper")),
                    'percent': percent_increase('daily_attendance', yesterday_data, before_yesterday_data),
                    'value': get_value(yesterday_data, 'daily_attendance'),
                    'all': get_value(yesterday_data, 'awcs'),
                    'format': 'div'
                },
                {
                    'label': _('Average number of forms hosuehold registration forms submitted yesterday'),
                    'help_text': _('Average number of household registration forms submitted by AWWs yesterday.'),
                    'percent': percent_increase('num_forms', yesterday_data, before_yesterday_data),
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
                    'percent': percent_increase('num_home_visits', yesterday_data, before_yesterday_data),
                    'value': get_value(yesterday_data, 'num_home_visits'),
                    'all': get_value(yesterday_data, 'awcs'),
                    'format': 'number'
                },
                {
                    'label': _('Average number of Growth Monitoring forms submitted yesterday'),
                    'help_text': _('Average number of growth monitoring forms (GMP) submitted yesterday'),
                    'percent': percent_increase('num_gmp', yesterday_data, before_yesterday_data),
                    'value': get_value(yesterday_data, 'num_gmp'),
                    'all': get_value(yesterday_data, 'awcs'),
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('Average number of Take Home Ration forms submitted yesterday'),
                    'help_text': _('Average number of Take Home Rations (THR) forms submitted yesterday'),
                    'percent': percent_increase('num_thr', yesterday_data, before_yesterday_data),
                    'value': get_value(yesterday_data, 'num_thr'),
                    'all': get_value(yesterday_data, 'awcs'),
                    'format': 'number'
                }
            ]
        ]
    }


@quickcache(['config'], timeout=24 * 60 * 60)
def get_maternal_child_data(config):

    def get_data_for_child_health_monhlty(date, filters):
        return AggChildHealthMonthly.objects.filter(
            month=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            underweight=(
                Sum('nutrition_status_moderately_underweight') + Sum('nutrition_status_severely_underweight')
            ),
            valid=Sum('valid_in_month'),
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

    this_month_data = get_data_for_child_health_monhlty(current_month, config)
    prev_month_data = get_data_for_child_health_monhlty(previous_month, config)

    deliveries_this_month = get_data_for_deliveries(current_month, config)
    deliveries_prev_month = get_data_for_deliveries(previous_month, config)

    return {
        'records': [
            [
                {
                    'label': _('% Underweight Children'),
                    'help_text': _((
                        "Percentage of children with weight-for-age less than -2 standard deviations of "
                        "the WHO Child Growth Standards median. Children who are moderately or severely "
                        "underweight have a higher risk of mortality.")
                    ),
                    'percent': percent_diff(
                        'underweight',
                        this_month_data,
                        prev_month_data,
                        'valid'
                    ),
                    'value': get_value(this_month_data, 'underweight'),
                    'all': get_value(this_month_data, 'valid'),
                    'format': 'percent_and_div'
                },
                {
                    'label': _('% Wasting'),
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
                    'format': 'percent_and_div'
                }
            ],
            [
                {
                    'label': _('% Stunting'),
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
                    'value': get_value(this_month_data, 'stunting_mod'),
                    'all': get_value(this_month_data, 'height_eli'),
                    'format': 'percent_and_div'
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
                    'format': 'percent_and_div'
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
                    'format': 'percent_and_div'
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
                    'format': 'percent_and_div'
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
                    'format': 'percent_and_div'
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
                    'format': 'percent_and_div'
                }
            ]
        ]
    }


def get_cas_reach_data(config):
    def get_data_for(month, filters):
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
                    'label': _('States/UTs covered'),
                    'help_text': _('Total States that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(this_month_data, 'states'),
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('Districts covered'),
                    'help_text': _('Total Districts that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(this_month_data, 'districts'),
                    'all': None,
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('Block covered'),
                    'help_text': _('Total Blocks that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(this_month_data, 'blocks'),
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('Sectors covered'),
                    'help_text': _('Total Sectors that have launched ICDS CAS'),
                    'percent': None,
                    'value': get_value(this_month_data, 'supervisors'),
                    'all': None,
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('AWCs covered'),
                    'help_text': _('Total AWCs that have launched ICDS CAS'),
                    'percent': percent_increase('awcs', this_month_data, prev_month_data),
                    'value': get_value(this_month_data, 'awcs'),
                    'all': None,
                    'format': 'number'
                }
            ]
        ]
    }


def get_demographics_data(yesterday, before_yesterday, config):
    def get_data_for(date, filters):
        return AggAwcDailyView.objects.filter(
            date=date, **filters
        ).values(
            'aggregation_level'
        ).annotate(
            household=Sum('cases_household'),
            child_health=Sum('cases_child_health'),
            ccs_pregnant=Sum('cases_ccs_pregnant'),
            css_lactating=Sum('cases_ccs_lactating'),
            person_adolescent=Sum('cases_person_adolescent'),
            person_aadhaar=Sum('cases_person_has_aadhaar'),
            all_persons=Sum('cases_person')
        )

    yesterday_data = get_data_for(datetime(*yesterday), config)
    before_yesterday_data = get_data_for(datetime(*before_yesterday), config)

    return {
        'records': [
            [
                {
                    'label': _('Registered Households'),
                    'help_text': _('Total number of households registered using ICDS CAS'),
                    'percent': None,
                    'value': get_value(yesterday_data, 'household'),
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('ICDS Beneficiary Households'),
                    'help_text': _('Total number of households that have consented to avail ICDS services'),
                    'percent': 0,
                    'value': 0,
                    'all': 0,
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('Children (0-6 years)'),
                    'help_text': _('Total number of children registered between the age of 0 - 6 years'),
                    'percent': None,
                    'value': get_value(yesterday_data, 'child_health'),
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('Pregnant Women'),
                    'help_text': _('Total number of pregnant women registered'),
                    'percent': None,
                    'value': get_value(yesterday_data, 'ccs_pregnant'),
                    'all': None,
                    'format': 'number'
                }
            ], [
                {
                    'label': _('Lactating Mothers'),
                    'help_text': _('Total number of lactating women registered'),
                    'percent': None,
                    'value': get_value(yesterday_data, 'css_lactating'),
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('Adolescent Girls (11-18 years)'),
                    'help_text': _('Total number of adolescent girls who are registered'),
                    'percent': None,
                    'value': get_value(yesterday_data, 'person_adolescent'),
                    'all': None,
                    'format': 'number'
                }
            ], [
                {
                    'label': _('% Adhaar seeded beneficaries'),
                    'help_text': _((
                        'Percentage of ICDS beneficiaries whose Adhaar identification has been captured'
                    )),
                    'percent': percent_diff(
                        'person_aadhaar',
                        yesterday_data,
                        before_yesterday_data,
                        'all_persons'
                    ),
                    'value': get_value(yesterday_data, 'person_aadhaar'),
                    'all': get_value(yesterday_data, 'all_persons'),
                    'format': 'number'
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
                    'label': _('Total number of AWCs with a source of clean drinking water'),
                    'help_text': _('Percentage of AWCs with a source of clean drinking water'),
                    'percent': percent_diff(
                        'clean_water',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': get_value(this_month_data, 'clean_water'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div'
                },
                {
                    'label': _((
                        "Total number of AWCs with a functional toilet (is a question in infrastructure "
                        "details form in AWC management module)")
                    ),
                    'help_text': _('Percentage of AWCs with a functional toilet'),
                    'percent': percent_diff(
                        'functional_toilet',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': get_value(this_month_data, 'functional_toilet'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div'
                }
            ],
            [
                {
                    'label': _('Total number of AWCs with access to electricity'),
                    'help_text': _('Percentage of AWCs with access to electricity'),
                    'percent': 0,
                    'value': 0,
                    'all': 0,
                    'format': 'percent_and_div'
                },
                {
                    'label': _('Total number of AWCs with a Medicine Kit'),
                    'help_text': _('Percentage of AWCs with a Medicine Kit'),
                    'percent': percent_diff(
                        'medicine_kits',
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': get_value(this_month_data, 'medicine_kits'),
                    'all': get_value(this_month_data, 'awcs'),
                    'format': 'percent_and_div'
                }
            ],
            [
                {
                    'label': _('Total number of AWCs with an infantometer'),
                    'help_text': _('Percentage of AWCs with an Infantometer'),
                    'percent': 0,
                    'value': 0,
                    'all': 0,
                    'format': 'percent_and_div'
                },
                {
                    'label': _('Total number of AWCs with a stadiometer'),
                    'help_text': _('Percentage of AWCs with a Stadiometer'),
                    'percent': 0,
                    'value': 0,
                    'all': 0,
                    'format': 'percent_and_div'
                }
            ],
            [
                {
                    'label': _('Total number of AWCs with a weighing scale'),
                    'help_text': _('Percentage of AWCs with a Weighing scale'),
                    'percent': 0,
                    'value': 0,
                    'all': 0,
                    'format': 'percent_and_div'
                }
            ]
        ]
    }


def get_awc_opened_data(filters):

    def get_data_for(date):
        return AggDailyUsageView.objects.filter(
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
                    '0%-50%': '#d60000',
                    '51%-75%': '#df7400',
                    '75%-100%': '#009811',
                    'defaultFill': '#9D9D9D',
                },
                "rightLegend": {
                    "average": num * 100 / (denom or 1),
                    "info": _("Percentage of Angwanwadi Centers that were open yesterday")
                },
                "data": data,
            }
        ]
    }


@quickcache(['config', 'loc_level'], timeout=24 * 60 * 60)
def get_prevalence_of_undernutrition_data_map(config, loc_level):
    if loc_level in [LocationTypes.BLOCK, LocationTypes.SUPERVISOR, LocationTypes.AWC]:
        return get_prevalence_of_undernutrition_sector_data(config, loc_level)

    def get_data_for(filters):
        filters['month'] = datetime(*filters['month'])
        return AggChildHealthMonthly.objects.filter(
            **filters
        ).values(
            '%s_name' % loc_level
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            valid=Sum('valid_in_month'),
        )

    map_data = {}
    average = []
    for row in get_data_for(config):
        valid = row['valid']
        name = row['%s_name' % loc_level]

        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']

        moderately_percent = (moderately_underweight or 0) * 100 / (valid or 1)
        severely_percent = (severely_underweight or 0) * 100 / (valid or 1)

        average.extend([moderately_percent, moderately_percent])

        if 0 <= moderately_percent < 16 or 0 <= severely_percent < 6:
            map_data.update({name: {'fillKey': '0%-15%'}})
        elif 16 <= moderately_percent <= 30 or 6 <= severely_percent <= 10:
            map_data.update({name: {'fillKey': '16%-30%'}})
        elif moderately_percent > 30 or severely_percent > 10:
            map_data.update({name: {'fillKey': '30%-100%'}})

    return [
        {
            "slug": "moderately_underweight",
            "label": "",
            "fills": {
                '0%-15%': '#009811',
                '16%-30%': '#df7400',
                '30%-100%': '#d60000',
                'defaultFill': '#9D9D9D',
            },
            "rightLegend": {
                "average": sum(average) / (len(average) or 1),
                "info": _((
                    "Percentage of children with weight-for-age less than -2 standard deviations of the WHO"
                    " Child Growth Standards median. Children who are moderately or severely underweight "
                    "have a higher risk of mortality."))
            },
            "data": map_data,
        }
    ]


def get_prevalence_of_undernutrition_data_chart(config, loc_level):
    config['month__range'] = (
        datetime(*config['month']) - relativedelta(months=3),
        datetime(*config['month'])
    )
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

    locations_for_lvl = SQLLocation.objects.filter(location_type__code=loc_level).count()

    data = {
        'green': {},
        'orange': {},
        'red': {}
    }
    best_worst = {}
    for row in chart_data:
        date = row['month']
        valid = row['valid']
        location = row['%s_name' % loc_level]
        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']

        moderately_percent = (moderately_underweight or 0) * 100 / (valid or 1)
        severely_percent = (severely_underweight or 0) * 100 / (valid or 1)

        if location in best_worst:
            best_worst[location].extend([moderately_percent, severely_percent])
        else:
            best_worst[location] = [moderately_percent, severely_percent]

        date_in_miliseconds = int(date.strftime("%s")) * 1000

        if date_in_miliseconds not in data['green']:
            data['green'][date_in_miliseconds] = 0
            data['orange'][date_in_miliseconds] = 0
            data['red'][date_in_miliseconds] = 0

        if 0 <= moderately_percent < 16 or 0 <= severely_percent < 6:
            data['green'][date_in_miliseconds] += 1
        elif 16 <= moderately_percent <= 30 or 6 <= severely_percent <= 10:
            data['orange'][date_in_miliseconds] += 1
        elif moderately_percent > 30 or severely_percent > 10:
            data['red'][date_in_miliseconds] += 1

    top_locations = sorted(
        [dict(loc_name=key, percent=sum(value) / len(value)) for key, value in best_worst.iteritems()],
        key=lambda x: x['percent'],
        reverse=True
    )

    return {
        "chart_data": [
            {
                "values": [[key, value / float(locations_for_lvl)] for key, value in data['green'].iteritems()],
                "key": "Between 0%-15%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": "#009811"
            },
            {
                "values": [[key, value / float(locations_for_lvl)] for key, value in data['orange'].iteritems()],
                "key": "Between 16%-30%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": "#df7400"
            },
            {
                "values": [[key, value / float(locations_for_lvl)] for key, value in data['red'].iteritems()],
                "key": "Between 31%-100%",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": "#d60000"
            }
        ],
        "top_three": top_locations[0:3],
        "bottom_three": top_locations[-4:-1],
        "location_type": loc_level.title()
    }


@quickcache(['config', 'loc_level'], timeout=24 * 60 * 60)
def get_prevalence_of_undernutrition_sector_data(config, loc_level):
    return {
        "chart_data": [
            {
                "values": [['Karera', 0.17], ['Koloras', 0.42], ['Pichhore', 0.11]],
                "key": "green",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": "#009811"
            },
            {
                "values": [['Karera', 0.6], ['Koloras', 0.13], ['Pichhore', 0.3]],
                "key": "orange",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": "#df7400"
            },
            {
                "values": [['Karera', 0.11], ['Koloras', 0.3], ['Pichhore', 0.1]],
                "key": "red",
                "strokeWidth": 2,
                "classed": "dashed",
                "color": "#d60000"
            }
        ]
    }


def get_awc_reports_system_usage(config, month, prev_month, three_month, loc_level):

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
        pse_date__range=(datetime(*three_month), datetime(*month)), **config
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
                    'format': 'number'
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
                    'format': 'percent_and_div'
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


def get_awc_reports_pse(config, month, three_month):

    map_image_data = DailyAttendanceView.objects.filter(
        pse_date__range=(datetime(*three_month), datetime(*month)), **config
    ).values('awc_name', 'form_location_lat', 'form_location_long', 'image_name')

    map_data = []
    image_data = []
    tmp_image = []
    img_count = 0
    count = 1
    for map_row in map_image_data:
        lat = map_row['form_location_lat']
        long = map_row['form_location_long']
        awc_name = map_row['awc_name']
        if lat and long:
            map_data.append({
                'name': awc_name,
                'radius': 3,
                'country': 'IND',
                'fillKey': 'green',
                'latitude': lat,
                'longitude': long
            })
        tmp_image.append({'id': count, 'image': 'http://unsplash.it/' + str(300 + count) + '/300'})
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
            'bubbles': map_data,
            'title': 'PSE Form Submissions',
            'data': [
                {
                    "slug": "pse_forms",
                    "label": "",
                    "fills": {
                        'green': 'green',
                        'defaultFill': '#9D9D9D',
                    },
                    "rightLegend": {
                    },
                    "data": None,
                }
            ]
        },
        'images': image_data
    }


def get_awc_reports_maternal_child(config, month, three_month):

    data = AggChildHealthMonthly.objects.filter(
        month__range=(datetime(*three_month), datetime(*month)), **config
    ).values(
        'month', 'aggregation_level'
    ).annotate(
        underweight=(
            Sum('nutrition_status_moderately_underweight') + Sum('nutrition_status_severely_underweight')
        ),
        valid_in_month=Sum('valid_in_month'),
        immunized=Sum('fully_immunized_on_time') + Sum('fully_immunized_late'),
        eligible=Sum('fully_immunized_eligible')
    ).order_by('month')

    prevalence = []
    immunized = []
    for row in data:
        month = row['month']
        month_in_milliseconds = int(month.strftime("%s")) * 1000
        prevalence.append([month_in_milliseconds, row['underweight'] / float(row['valid_in_month'] or 1)])
        immunized.append([month_in_milliseconds, row['immunized'] / float(row['eligible'] or 1)])
    return {
        'charts': [
            [
                {
                    'key': 'Prevalence of undernutrition (weight-for-age)',
                    'values': prevalence,
                    "classed": "dashed",
                }
            ],
            [
                {
                    'key': '% Immunization coverage (at age 1 year)',
                    'values': immunized,
                    "classed": "dashed",
                }
            ]
        ]
    }


def get_awc_report_demographics(config, month):

    # map_data = AggAwcMonthly.objects.filter(
    #     month=datetime(*month), **config
    # ).values(
    #     'month', 'aggregation_level'
    # ).annotate(
    #     household=Sum('household')
    # ).order_by('month')
    #
    chart = AggChildHealthMonthly.objects.filter(
        month=datetime(*month), **config
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
            adolescent=Sum('cases_person_adolescent'),
            has_aadhaar=Sum('cases_person_has_aadhaar'),
            all_cases=Sum('cases_person')
        )

    yesterday = datetime.now() - relativedelta(days=1)
    before_yesterday = yesterday - relativedelta(days=1)
    kpi_yesterday = get_data_for_kpi(config, yesterday.date())
    kpi_before_yesterday = get_data_for_kpi(config, before_yesterday.date())
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
                    'label': _('Pregnant Women'),
                    'help_text': _("Total number of pregnant women registered"),
                    'percent': percent_increase(
                        'ccs_pregnant',
                        kpi_yesterday,
                        kpi_before_yesterday,
                    ),
                    'value': get_value(kpi_yesterday, 'ccs_pregnant'),
                    'all': '',
                    'format': 'number'
                },
                {
                    'label': _('Lactating Mothers'),
                    'help_text': _('Total number of lactating women registered'),
                    'percent': percent_increase(
                        ['ccs_lactating'],
                        kpi_yesterday,
                        kpi_before_yesterday
                    ),
                    'value': get_value(kpi_yesterday, 'ccs_lactating'),
                    'all': '',
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('Adolescent Girls (11-18 years)'),
                    'help_text': _('Total number of adolescent girls who are registered'),
                    'percent': percent_increase(
                        'adolescent',
                        kpi_yesterday,
                        kpi_before_yesterday,
                    ),
                    'value': get_value(kpi_yesterday, 'adolescent'),
                    'all': '',
                    'format': 'number'
                },
                {
                    'label': _('% Adhaar seeded beneficaries'),
                    'help_text': _(
                        'Percentage of ICDS beneficiaries whose Adhaar identification has been captured'
                    ),
                    'percent': percent_diff(
                        ['has_aadhaar'],
                        kpi_yesterday,
                        kpi_before_yesterday,
                        'all_cases'
                    ),
                    'value': get_value(kpi_yesterday, 'has_aadhaar'),
                    'all': get_value(kpi_yesterday, 'all_cases'),
                    'format': 'div'
                }
            ]
        ]
    }
