from __future__ import absolute_import, division
import json
import os
import zipfile

from collections import defaultdict
from datetime import datetime, timedelta

import operator

from six.moves import cStringIO
from dateutil.relativedelta import relativedelta
from django.template.loader import render_to_string, get_template
from xhtml2pdf import pisa

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_latest_released_build_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import StaticReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.util.quickcache import quickcache
from custom.icds_reports.const import ISSUE_TRACKER_APP_ID, LOCATION_TYPES
from custom.icds_reports.queries import get_test_state_locations_id
from dimagi.utils.couch import get_redis_client
from dimagi.utils.dates import DateSpan
from django.db.models import Case, When, Q, F, IntegerField
import six
import uuid

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": operator.contains,
}

RED = '#de2d26'
ORANGE = '#fc9272'
BLUE = '#006fdf'
PINK = '#fee0d2'
GREY = '#9D9D9D'

DEFAULT_VALUE = "Data not Entered"

DATA_NOT_ENTERED = "Data Not Entered"

class MPRData(object):
    resource_file = 'resources/block_mpr.json'


class ASRData(object):
    resource_file = 'resources/block_asr.json'


class ICDSData(object):

    def __init__(self, domain, filters, report_id):
        report_config = ReportFactory.from_spec(
            self._get_static_report_configuration_without_owner_transform(report_id.format(domain=domain))
        )
        report_config.set_filter_values(filters)
        self.report_config = report_config

    def _get_static_report_configuration_without_owner_transform(self, report_id):
        static_report_configuration = StaticReportConfiguration.by_id(report_id)
        for report_column in static_report_configuration.report_columns:
            transform = report_column.transform
            if transform.get('type') == 'custom' and transform.get('custom_type') == 'owner_display':
                report_column.transform = {}
        return static_report_configuration

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
                        if isinstance(v, six.string_types):
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
    return ((current_percent - prev_percent) / (prev_percent or 1.0)) * 100


def get_value(data, prop):
    return (data[0][prop] or 0) if data else 0


def apply_exclude(domain, queryset):
    return queryset.exclude(
        state_id__in=get_test_state_locations_id(domain)
    )


def get_age_filter(age_value):
    """
        When age_value = 6 it means first range is chosen 0-6 months.
        For that range we want to include 0 and 6 in results.
    """
    if age_value == '6':
        return {'age_tranche__in': ['0', '6']}
    else:
        return {'age_tranche': age_value}


def match_age(age):
    if 0 <= age <= 1:
        return '0-1 month'
    elif 1 < age <= 6:
        return '1-6 months'
    elif 6 < age <= 12:
        return '6-12 months'
    elif 12 < age <= 36:
        return '1-3 years'
    elif 36 < age <= 72:
        return '3-6 years'


def get_location_filter(location_id, domain):
    """
    Args:
        location_id (str)
        domain (str)
    Returns:
        dict
    """
    if not location_id:
        return {}

    config = {}
    try:
        sql_location = SQLLocation.objects.get(location_id=location_id, domain=domain)
    except SQLLocation.DoesNotExist:
        return {'aggregation_level': 1}
    config.update(
        {
            ('%s_id' % ancestor.location_type.code): ancestor.location_id
            for ancestor in sql_location.get_ancestors(include_self=True)
        }
    )
    config['aggregation_level'] = len(config) + 1
    return config


def get_location_level(aggregation_level):
    if not aggregation_level:
        return LOCATION_TYPES[0]
    elif aggregation_level >= len(LOCATION_TYPES):
        return LOCATION_TYPES[-1]
    return LOCATION_TYPES[aggregation_level - 1]


@quickcache([])
def get_latest_issue_tracker_build_id():
    return get_latest_released_build_id('icds-cas', ISSUE_TRACKER_APP_ID)


def get_status(value, second_part='', normal_value='', exportable=False):
    status = {'value': DATA_NOT_ENTERED, 'color': 'black'}
    if not value or value in ['unweighed', 'unmeasured', 'unknown']:
        status = {'value': DATA_NOT_ENTERED, 'color': 'black'}
    elif value in ['severely_underweight', 'severe']:
        status = {'value': 'Severely ' + second_part, 'color': 'red'}
    elif value in ['moderately_underweight', 'moderate']:
        status = {'value': 'Moderately ' + second_part, 'color': 'black'}
    elif value in ['normal']:
        status = {'value': normal_value, 'color': 'black'}
    return status if not exportable else status['value']


def current_age(dob, selected_date):
    age = relativedelta(selected_date, dob)
    age_format = ""
    if age.years:
        age_format += "%s year%s " % (age.years, '' if age.years == 1 else 's')
    if age.months:
        age_format += "%s month%s " % (age.months, '' if age.months == 1 else 's')
    if not age.years and not age.months:
        if age.days > 0:
            age_format = "%s day%s" % (age.days, '' if age.days == 1 else 's')
        else:
            age_format = "0 days"
    return age_format


def exclude_records_by_age_for_column(exclude_config, column):
    return Case(
        When(~Q(**exclude_config), then=F(column)),
        default=0,
        output_field=IntegerField()
    )


def generate_data_for_map(data, loc_level, num_prop, denom_prop, fill_key_lower, fill_key_bigger):
    data_for_map = defaultdict(lambda: {
        num_prop: 0,
        denom_prop: 0,
        'original_name': []
    })

    valid_total = 0
    in_month_total = 0

    for row in data:
        valid = row[denom_prop] or 0
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name
        in_month = row[num_prop] or 0

        valid_total += valid
        in_month_total += in_month

        data_for_map[on_map_name][num_prop] += in_month
        data_for_map[on_map_name][denom_prop] += valid
        if name != on_map_name:
            data_for_map[on_map_name]['original_name'].append(name)

    for data_for_location in six.itervalues(data_for_map):
        value = data_for_location[num_prop] * 100 / (data_for_location[denom_prop] or 1)
        fill_format = '%s%%-%s%%'
        if value < fill_key_lower:
            data_for_location.update({'fillKey': (fill_format % (0, fill_key_lower))})
        elif fill_key_lower <= value < fill_key_bigger:
            data_for_location.update({'fillKey': (fill_format % (fill_key_lower, fill_key_bigger))})
        elif value >= fill_key_bigger:
            data_for_location.update({'fillKey': (fill_format % (fill_key_bigger, 100))})

    return data_for_map, valid_total, in_month_total


def calculate_date_for_age(dob, date):
    now = datetime.utcnow().date()
    if now.month == date.month and now.year == date.year:
        date_for_age = now
    else:
        date_for_age = (date + relativedelta(months=1)) - relativedelta(days=1)
    return current_age(dob, date_for_age)


def chosen_filters_to_labels(config, default_interval=''):
    gender_types = {
        'M': 'Male',
        'F': 'Female'
    }

    age_intervals = {
        '6': '0-6 months',
        '12': '6-12 months',
        '24': '12-24 months',
        '36': '24-36 months',
        '48': '36-48 months',
        '60': '48-60 months',
        '72': '60-72 months'
    }

    gender = config.get('gender')
    gender_label = ' ({gender})'.format(gender=gender_types.get(gender)) if gender else ''
    chosen_gender = '{gender}'.format(gender=gender_types.get(gender)) if gender else ''

    age = config.get('age_tranche')
    age_in = config.get('age_tranche__in')
    if age:
        chosen_age = '{age}'.format(age=age_intervals.get(age))
    elif age_in:
        chosen_age = '{age}'.format(age=age_intervals.get(age_in[-1]))
    else:
        chosen_age = ''
    age_label = chosen_age if chosen_age else default_interval

    delimiter = ', ' if gender and (age or age_in) else ''
    chosen_filters = ' ({gender}{delimiter}{age})'\
        .format(gender=chosen_gender, delimiter=delimiter, age=chosen_age) if gender or age else ''

    return gender_label, age_label, chosen_filters


def zip_folder(pdf_files):
    zip_hash = uuid.uuid4().hex
    client = get_redis_client()
    in_memory = cStringIO.StringIO()
    zip_file = zipfile.ZipFile(in_memory, 'w', zipfile.ZIP_DEFLATED)
    for pdf_file in pdf_files:
        file = client.get(pdf_file['uuid'])
        zip_file.writestr('ISSNIP_monthly_register_{}.pdf'.format(pdf_file['location_name']), file)
    zip_file.close()
    client.set(zip_hash, in_memory.getvalue())
    return zip_hash


def create_pdf_file(pdf_hash, pdf_context):
    template = get_template("icds_reports/icds_app/pdf/issnip_monthly_register.html")
    resultFile = cStringIO.StringIO()
    client = get_redis_client()
    pisa.CreatePDF(
        template.render(pdf_context),
        dest=resultFile)
    client.set(pdf_hash, resultFile.getvalue())
    client.expire(pdf_hash, 24 * 60 * 60)
    resultFile.close()
    return pdf_hash


def icds_pre_release_features(user):
    return toggles.ICDS_DASHBOARD_REPORT_FEATURES.enabled(user.username)


def indian_formatted_number(number):
    s = str(number)
    if s.isdigit():
        r = ",".join([s[x - 2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return "".join(r)
    else:
        return 0
