import json
import os

from datetime import datetime, timedelta

import operator

from dateutil.relativedelta import relativedelta

from corehq.util.quickcache import quickcache
from django.db.models.aggregates import Sum
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import StaticReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from dimagi.utils.dates import DateSpan

from custom.icds_reports.models import AggDailyUsageView, AggChildHealthMonthly, AggAwcMonthly, AggCcsRecordMonthly, \
    AggAwcDailyView

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
    current = prev_data[0][prop]
    previous = data[0][prop]
    return ((current or 0) - (previous or 0)) / float(previous or 1) * 100


def percent_diff(properties, current_data, prev_data, all):
    current = 0
    prev = 0
    for prop in properties:
        current = current_data[0][prop]
        prev = prev_data[0][prop]
    current_percent = (current or 0) / float(current_data[0][all] or 1) * 100
    prev_percent = (prev or 0) / float(prev_data[0][all] or 1) * 100
    return current_percent - prev_percent


def get_system_usage_data(filters):

    def get_data_for(date):
        return AggDailyUsageView.objects.filter(
            date=datetime(*date), aggregation_level=1
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

    yesterday_data = get_data_for(filters['yesterday'])
    before_yesterday_data = get_data_for(filters['before_yesterday'])

    return {
        'records': [
            [
                {
                    'label': _('Number of AWCs Open yesterday'),
                    'help_text': _(("Total Number of Angwanwadi Centers that were open yesterday "
                                    "by the AWW or the AWW helper")),
                    'percent': percent_increase('daily_attendance', yesterday_data, before_yesterday_data),
                    'value': yesterday_data[0]['daily_attendance'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'div'
                },
                {
                    'label': _('Average number of forms hosuehold registration forms submitted yesterday'),
                    'help_text': _('Average number of household registration forms submitted by AWWs yesterday.'),
                    'percent': percent_increase('num_forms', yesterday_data, before_yesterday_data),
                    'value': yesterday_data[0]['num_forms'],
                    'all': yesterday_data[0]['awcs'],
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
                    'value': yesterday_data[0]['num_home_visits'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'number'
                },
                {
                    'label': _('Average number of Growth Monitoring forms submitted yesterday'),
                    'help_text': _('Average number of growth monitoring forms (GMP) submitted yesterday'),
                    'percent': percent_increase('num_gmp', yesterday_data, before_yesterday_data),
                    'value': yesterday_data[0]['num_gmp'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'number'
                }
            ], [
                {
                    'label': _('Average number of Take Home Ration forms submitted yesterday'),
                    'help_text': _('Average number of Take Home Rations (THR) forms submitted yesterday'),
                    'percent': percent_increase('num_thr', yesterday_data, before_yesterday_data),
                    'value': yesterday_data[0]['num_thr'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'number'
                }
            ]
        ]
    }


@quickcache(['filters'], timeout=24 * 60 * 60)
def get_maternal_child_data(filters):

    def get_data_for(month):
        return AggChildHealthMonthly.objects.filter(
            month=datetime(*month), aggregation_level=1
        ).values(
            'aggregation_level'
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            valid=Sum('valid_in_month'),
            wasting_mod=Sum('wasting_moderate'),
            wasting_seve=Sum('wasting_severe'),
            stunting_mod=Sum('stunting_moderate'),
            stunting_seve=Sum('stunting_severe'),
            height_eli=Sum('height_eligible'),
            low_birth_weight=Sum('low_birth_weight_in_month'),
            bf_birth=Sum('bf_at_birth'),
            born=Sum('born_in_month'),
            ebf=Sum('ebf_in_month'),
            ebf_eli=Sum('ebf_eligible'),
            cf_initiation=Sum('cf_initiation_in_month'),
            cf_initiation_eli=Sum('cf_initiation_eligible')
        )

    this_month_data = get_data_for(filters['month'])
    prev_month_data = get_data_for(filters['prev_month'])

    deliveries_this_month = AggCcsRecordMonthly.objects.filter(
        month=datetime(*filters['month']), aggregation_level=1
    ).values(
        'aggregation_level'
    ).annotate(
        institutional_delivery=Sum('institutional_delivery_in_month'),
        delivered=Sum('delivered_in_month')
    )

    deliveries_prev_month = AggCcsRecordMonthly.objects.filter(
        month=datetime(*filters['prev_month']), aggregation_level=1
    ).values(
        'aggregation_level'
    ).annotate(
        institutional_delivery=Sum('institutional_delivery_in_month'),
        delivered=Sum('delivered_in_month')
    )

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
                        ['moderately_underweight', 'severely_underweight'],
                        this_month_data,
                        prev_month_data,
                        'valid'
                    ),
                    'value': (
                        this_month_data[0]['moderately_underweight'] + this_month_data[0]['severely_underweight']
                    ),
                    'all': this_month_data[0]['valid'],
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
                        ['wasting_mod', 'wasting_seve'],
                        this_month_data,
                        prev_month_data,
                        'height_eli'
                    ),
                    'value': this_month_data[0]['wasting_mod'] + this_month_data[0]['wasting_seve'],
                    'all': this_month_data[0]['height_eli'],
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
                        ['stunting_mod', 'stunting_seve'],
                        this_month_data,
                        prev_month_data,
                        'height_eli'
                    ),
                    'value': this_month_data[0]['stunting_mod'] + this_month_data[0]['stunting_seve'],
                    'all': this_month_data[0]['height_eli'],
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
                        ['low_birth_weight'],
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'value': this_month_data[0]['low_birth_weight'],
                    'all': this_month_data[0]['born'],
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
                        ['bf_birth'],
                        this_month_data,
                        prev_month_data,
                        'born'
                    ),
                    'value': this_month_data[0]['bf_birth'],
                    'all': this_month_data[0]['born'],
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
                        ['ebf'],
                        this_month_data,
                        prev_month_data,
                        'ebf_eli'
                    ),
                    'value': this_month_data[0]['ebf'],
                    'all': this_month_data[0]['ebf_eli'],
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
                        ['cf_initiation'],
                        this_month_data,
                        prev_month_data,
                        'cf_initiation_eli'
                    ),
                    'value': this_month_data[0]['cf_initiation'],
                    'all': this_month_data[0]['cf_initiation_eli'],
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
                        ['institutional_delivery'],
                        deliveries_this_month,
                        deliveries_prev_month,
                        'delivered'
                    ),
                    'value': deliveries_this_month[0]['institutional_delivery'] or 0,
                    'all': deliveries_this_month[0]['delivered'] or 0,
                    'format': 'percent_and_div'
                }
            ]
        ]
    }


def get_cas_reach_data(filters):
    def get_data_for(month):
        return AggAwcMonthly.objects.filter(
            month=datetime(*month), aggregation_level=1
        ).values(
            'aggregation_level'
        ).annotate(
            states=Sum('num_launched_states'),
            districts=Sum('num_launched_districts'),
            blocks=Sum('num_launched_blocks'),
            supervisors=Sum('num_launched_supervisors'),
            awcs=Sum('num_launched_awcs'),

        )

    this_month_data = get_data_for(filters['month'])
    prev_month_data = get_data_for(filters['prev_month'])

    return {
        'records': [
            [
                {
                    'label': _('States/UTs covered'),
                    'help_text': _('Total States that have launched ICDS CAS'),
                    'percent': None,
                    'value': this_month_data[0]['states'],
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('Districts covered'),
                    'help_text': _('Total Districts that have launched ICDS CAS'),
                    'percent': None,
                    'value': this_month_data[0]['districts'],
                    'all': None,
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('Block covered'),
                    'help_text': _('Total Blocks that have launched ICDS CAS'),
                    'percent': None,
                    'value': this_month_data[0]['blocks'],
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('Sectors covered'),
                    'help_text': _('Total Sectors that have launched ICDS CAS'),
                    'percent': None,
                    'value': this_month_data[0]['supervisors'],
                    'all': None,
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('AWCs covered'),
                    'help_text': _('Total AWCs that have launched ICDS CAS'),
                    'percent': percent_increase('awcs', this_month_data, prev_month_data),
                    'value': this_month_data[0]['awcs'],
                    'all': None,
                    'format': 'number'
                }
            ]
        ]
    }


def get_demographics_data(filters):
    def get_data_for(date):
        return AggAwcDailyView.objects.filter(
            date=datetime(*date), aggregation_level=1
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

    yesterday_data = get_data_for(filters['yesterday'])
    before_yesterday_data = get_data_for(filters['before_yesterday'])

    return {
        'records': [
            [
                {
                    'label': _('Registered Households'),
                    'help_text': _('Total number of households registered using ICDS CAS'),
                    'percent': None,
                    'value': yesterday_data[0]['household'],
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
                    'value': yesterday_data[0]['child_health'],
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('Pregnant Women'),
                    'help_text': _('Total number of pregnant women registered'),
                    'percent': None,
                    'value': yesterday_data[0]['ccs_pregnant'],
                    'all': None,
                    'format': 'number'
                }
            ], [
                {
                    'label': _('Lactating Mothers'),
                    'help_text': _('Total number of lactating women registered'),
                    'percent': None,
                    'value': yesterday_data[0]['css_lactating'],
                    'all': None,
                    'format': 'number'
                },
                {
                    'label': _('Adolescent Girls (11-18 years)'),
                    'help_text': _('Total number of adolescent girls who are registered'),
                    'percent': None,
                    'value': yesterday_data[0]['person_adolescent'],
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
                        ['person_aadhaar'],
                        yesterday_data,
                        before_yesterday_data,
                        'all_persons'
                    ),
                    'value': yesterday_data[0]['person_aadhaar'],
                    'all': yesterday_data[0]['all_persons'],
                    'format': 'number'
                }
            ]
        ]
    }


def get_awc_infrastructure_data(filters):
    def get_data_for(month):
        return AggAwcMonthly.objects.filter(
            month=datetime(*month), aggregation_level=1
        ).values(
            'aggregation_level'
        ).annotate(
            clean_water=Sum('infra_clean_water'),
            functional_toilet=Sum('infra_functional_toilet'),
            medicine_kits=Sum('infra_medicine_kits'),
            awcs=Sum('num_awcs')
        )

    this_month_data = get_data_for(filters['month'])
    prev_month_data = get_data_for(filters['prev_month'])

    return {
        'records': [
            [
                {
                    'label': _('Total number of AWCs with a source of clean drinking water'),
                    'help_text': _('Percentage of AWCs with a source of clean drinking water'),
                    'percent': percent_diff(
                        ['clean_water'],
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': this_month_data[0]['clean_water'],
                    'all': this_month_data[0]['awcs'],
                    'format': 'percent_and_div'
                },
                {
                    'label': _((
                        "Total number of AWCs with a functional toilet (is a question in infrastructure "
                        "details form in AWC management module)")
                    ),
                    'help_text': _('Percentage of AWCs with a functional toilet'),
                    'percent': percent_diff(
                        ['functional_toilet'],
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': this_month_data[0]['functional_toilet'],
                    'all': this_month_data[0]['awcs'],
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
                        ['medicine_kits'],
                        this_month_data,
                        prev_month_data,
                        'awcs'
                    ),
                    'value': this_month_data[0]['medicine_kits'],
                    'all': this_month_data[0]['awcs'],
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
                    'defaultFill': '#eef2ff',
                },
                "rightLegend": {
                    "average": num * 100 / (denom or 1),
                    "info": _("Percentage of Angwanwadi Centers that were open yesterday")
                },
                "data": data,
            }
        ]
    }


def get_prevalnece_of_undernutrition_data(filters):

    def get_data_for(month):
        return AggChildHealthMonthly.objects.filter(
            month=datetime(*month), aggregation_level=1
        ).values(
            'state_name'
        ).annotate(
            moderately_underweight=Sum('nutrition_status_moderately_underweight'),
            severely_underweight=Sum('nutrition_status_severely_underweight'),
            valid=Sum('valid_in_month'),
        )

    map_data = {}
    average = []
    for row in get_data_for(filters['month']):
        valid = row['valid']
        name = row['state_name']

        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']

        average.extend([severely_underweight, moderately_underweight])

        moderately_percent = (moderately_underweight or 0) * 100 / (valid or 1)
        severely_percent = (severely_underweight or 0) * 100 / (valid or 1)
        if 0 <= moderately_percent < 16 or 0 <= severely_percent < 6:
            map_data.update({name: {'fillKey': '0%-15%'}})
        elif 16 <= moderately_percent <= 30 or 6 <= severely_percent <= 10:
            map_data.update({name: {'fillKey': '16%-30%'}})
        elif moderately_percent > 30 or severely_percent > 10:
            map_data.update({name: {'fillKey': '30%-100%'}})


    moderately_chart_data = []
    severaly_chart_data = []

    chart_data = AggChildHealthMonthly.objects.filter(
        month__range=(
            datetime(*filters['month']) - relativedelta(months=3),
            datetime(*filters['month'])
        ), aggregation_level=1
    ).values(
        'month',
    ).annotate(
        moderately_underweight=Sum('nutrition_status_moderately_underweight'),
        severely_underweight=Sum('nutrition_status_severely_underweight'),
        valid=Sum('valid_in_month'),
    ).order_by('month')

    for row in chart_data:
        date = row['month']
        valid = row['valid']
        severely_underweight = row['severely_underweight']
        moderately_underweight = row['moderately_underweight']

        average.extend([severely_underweight, moderately_underweight])

        moderately_percent = (moderately_underweight or 0) / float(valid or 1)
        severely_percent = (severely_underweight or 0) / float(valid or 1)

        moderately_chart_data.append([int(date.strftime("%s")) * 1000, moderately_percent])
        severaly_chart_data.append([int(date.strftime("%s")) * 1000, severely_percent])

    return {
        "configs": [
            {
                "slug": "moderately_underweight",
                "label": "",
                "fills": {
                    '0%-15%': '#009811',
                    '16%-30%': '#df7400',
                    '30%-100%': '#d60000',
                    'defaultFill': '#eef2ff',
                },
                "rightLegend": {
                    "average": sum(average) / len(average),
                    "info": _((
                        "Percentage of children with weight-for-age less than -2 standard deviations of the WHO"
                        " Child Growth Standards median. Children who are moderately or severely underweight "
                        "have a higher risk of mortality."))
                },
                "data": map_data,
            }
        ],
        "chart": [
            {
                "values": moderately_chart_data,
                "key": "Underweight below -2 Z score",
                "strokeWidth": 2,
                "classed": "dashed"
            },
            {
                "values": severaly_chart_data,
                "key": "Underweight below -3 Z score",
                "strokeWidth": 2,
                "classed": "dashed"
            }
        ]
    }