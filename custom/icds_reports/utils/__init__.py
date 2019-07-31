from __future__ import absolute_import, division
from __future__ import unicode_literals
import json
import os
import string
import time
import zipfile

from collections import defaultdict
from datetime import datetime, timedelta, date
from functools import wraps
from memoized import memoized

import operator

import pytz
import qrcode
from base64 import b64encode
from io import BytesIO
from dateutil.relativedelta import relativedelta
from django.template.loader import render_to_string, get_template
from django.conf import settings
from openpyxl.styles import PatternFill, Border, Side, Alignment, Font
from openpyxl import Workbook
from weasyprint import HTML, CSS

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_latest_released_build_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import StaticReportConfiguration, AsyncIndicator
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
from corehq.blobs.mixin import safe_id
from corehq.const import ONE_DAY
from corehq.util.datadog.gauges import datadog_histogram
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext
from custom.icds_reports import const
from custom.icds_reports.const import ISSUE_TRACKER_APP_ID, LOCATION_TYPES
from custom.icds_reports.models.helper import IcdsFile
from custom.icds_reports.queries import get_test_state_locations_id, get_test_district_locations_id
from couchexport.export import export_from_tables
from dimagi.utils.dates import DateSpan
from django.db.models import Case, When, Q, F, IntegerField, Max, Min
from django.db.utils import OperationalError
import six
import uuid
from six.moves import range
from sqlagg.filters import EQ, NOT, AND
from io import open
from pillowtop.models import KafkaCheckpoint
from six.moves import zip


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


DATA_NOT_ENTERED = "Data Not Entered"
DEFAULT_VALUE = DATA_NOT_ENTERED
DATA_NOT_VALID = "Data Not Valid"

india_timezone = pytz.timezone('Asia/Kolkata')


class MPRData(object):
    resource_file = ('custom', 'icds_reports', 'resources', 'block_mpr.json')


class ASRData(object):
    resource_file = ('custom', 'icds_reports', 'resources', 'block_asr.json')


class ICDSData(object):

    def __init__(self, domain, filters, report_id, override_agg_column=None):
        report_config = ConfigurableReportDataSource.from_spec(
            self._get_static_report_configuration_without_owner_transform(report_id, domain, override_agg_column)
        )
        report_config.set_filter_values(filters)
        self.report_config = report_config

    def _get_static_report_configuration_without_owner_transform(self, report_id, domain, override_agg_column):
        report_id = report_id.format(domain=domain)
        static_report_configuration = StaticReportConfiguration.by_id(report_id, domain)

        if override_agg_column and override_agg_column != 'awc_id':
            static_report_configuration = self._override_agg(static_report_configuration, override_agg_column)

        # this is explicitly after override, otherwise 'report_columns' attrib gets memoized too early
        for report_column in static_report_configuration.report_columns:
            transform = report_column.transform
            if transform.get('type') == 'custom' and transform.get('custom_type') == 'owner_display':
                report_column.transform = {}
        return static_report_configuration

    def _override_agg(self, static_report_configuration, override_agg_column):
        level_order = ['owner_id', 'awc_id', 'supervisor_id', 'block_id', 'district_id', 'state_id']
        # override aggregation level
        static_report_configuration.aggregation_columns = [override_agg_column]
        # remove columns below agg level
        columns_to_remove = level_order[0:level_order.index(override_agg_column)]
        for column in static_report_configuration.columns:
            if column.get('column_id') in columns_to_remove:
                static_report_configuration.columns.remove(column)
        return static_report_configuration

    def data(self):
        return self.report_config.get_data()


class ICDSMixin(object):
    has_sections = False
    posttitle = None

    def __init__(self, config, allow_conditional_agg=False):
        self.config = config
        self.allow_conditional_agg = allow_conditional_agg

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
        with open(os.path.join(*self.resource_file), encoding='utf-8') as f:
            return json.loads(f.read())[self.slug]

    @property
    @memoized
    def selected_location(self):
        if self.config['location_id']:
            return SQLLocation.objects.get(
                location_id=self.config['location_id']
            )

    @property
    @memoized
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

    @memoized
    def custom_data(self, selected_location, domain):
        timer = TimingContext()
        with timer:
            to_ret = self._custom_data(selected_location, domain)
        if selected_location:
            loc_type = selected_location.location_type.name
        else:
            loc_type = None
        tags = ["location_type:{}".format(loc_type), "report_slug:{}".format(self.slug)]
        if self.allow_conditional_agg:
            tags.append("allow_conditional_agg:yes")
        datadog_histogram(
            "commcare.icds.block_reports.custom_data_duration",
            timer.duration,
            tags=tags
        )
        return to_ret

    def _custom_data(self, selected_location, domain):
        data = {}

        for config in self.sources['data_source']:
            filters = {}
            location_type_column = None
            if selected_location:
                location_type_column = selected_location.location_type.name.lower() + '_id'
                filters = {
                    location_type_column: [Choice(value=selected_location.location_id, display=selected_location.name)]
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

            timer = TimingContext()
            with timer:
                allow_conditional_agg = self.allow_conditional_agg and not config.get('disallow_conditional_agg', False)
                override_agg_column = location_type_column if allow_conditional_agg else None
                report_data = ICDSData(domain, filters, config['id'], override_agg_column).data()
            if selected_location:
                loc_type = selected_location.location_type.name
            else:
                loc_type = None
            tags = ["location_type:{}".format(loc_type), "report_slug:{}".format(self.slug), "config:{}".format(config['id'])]
            if allow_conditional_agg:
                tags.append("allow_conditional_agg:yes")
            datadog_histogram(
                "commcare.icds.block_reports.ucr_querytime",
                timer.duration,
                tags=tags
            )

            for column in config['columns']:
                column_agg_func = column['agg_fun']
                column_name = column['column_name']
                column_data = 0
                if column_agg_func == 'sum':
                    column_data = sum([x.get(column_name, 0) or 0 for x in report_data])
                elif column_agg_func == 'count':
                    column_data = len(report_data)
                elif column_agg_func == 'count_if':
                    value = column['condition']['value']
                    op = column['condition']['operator']

                    def check_condition(v):
                        if isinstance(v, six.string_types):
                            soft_assert_type_text(v)
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


PREVIOUS_PERIOD_ZERO_DATA = "Data in the previous reporting period was 0"


def percent_increase(prop, data, prev_data):
    current = 0
    previous = 0
    if data:
        current = data[0][prop]
    if prev_data:
        previous = prev_data[0][prop]

    if previous:
        tenths_of_promils = (((current or 0) - (previous or 0)) * 10000) / float(previous or 1)
        return tenths_of_promils / 100 if (tenths_of_promils < -1 or 1 < tenths_of_promils) else 0
    else:
        return PREVIOUS_PERIOD_ZERO_DATA


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

    if prev_percent:
        tenths_of_promils = ((current_percent - prev_percent) * 10000) / (prev_percent or 1.0)
        return tenths_of_promils / 100 if (tenths_of_promils < -1 or 1 < tenths_of_promils) else 0
    else:
        return PREVIOUS_PERIOD_ZERO_DATA


def get_color_with_green_positive(val):
    if isinstance(val, (int, float)):
        if val > 0:
            return 'green'
        else:
            return 'red'
    else:
        assert val == PREVIOUS_PERIOD_ZERO_DATA, val
        return 'green'


def get_color_with_red_positive(val):
    if isinstance(val, (int, float)):
        if val > 0:
            return 'red'
        else:
            return 'green'
    else:
        assert val == PREVIOUS_PERIOD_ZERO_DATA, val
        return 'red'


def get_value(data, prop):
    return (data[0][prop] or 0) if data else 0


def apply_exclude(domain, queryset):
    return queryset.exclude(
        Q(state_id__in=get_test_state_locations_id(domain)) |
        Q(district_id__in=get_test_district_locations_id(domain))
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


def get_age_filter_in_months(age_value):
    """
        When age_value = 6 it means first range is chosen 0-6 months.
        For that range we want to include 0 and 6 in results.
    """
    if age_value == '6':
        return {'age_in_months__range': ['0', '6']}
    elif age_value == '12':
        return {'age_in_months__range': ['7', '12']}
    elif age_value == '24':
        return {'age_in_months__range': ['13', '24']}
    elif age_value == '36':
        return {'age_in_months__range': ['25', '36']}
    elif age_value == '48':
        return {'age_in_months__range': ['37', '48']}
    elif age_value == '60':
        return {'age_in_months__range': ['49', '60']}
    elif age_value == '72':
        return {'age_in_months__range': ['61', '72']}


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


def get_status(value, second_part='', normal_value='', exportable=False, data_entered=False):
    status = {'value': DATA_NOT_VALID if data_entered else DATA_NOT_ENTERED, 'color': 'black'}
    if not value or value in ['unweighed', 'unmeasured', 'unknown']:
        status = {'value': DATA_NOT_VALID if data_entered else DATA_NOT_ENTERED, 'color': 'black'}
    elif value in ['severely_underweight', 'severe']:
        status = {'value': 'Severely ' + second_part, 'color': 'red'}
    elif value in ['moderately_underweight', 'moderate']:
        status = {'value': 'Moderately ' + second_part, 'color': 'black'}
    elif value in ['normal']:
        status = {'value': normal_value, 'color': 'black'}
    return status if not exportable else status['value']


def is_anemic(value):
    if value['anemic_severe']:
        return 'Y'
    elif value['anemic_moderate']:
        return 'Y'
    elif value['anemic_normal']:
        return 'N'
    else:
        return DATA_NOT_ENTERED


def get_anemic_status(value):
    if value['anemic_severe']:
        return 'Severe'
    elif value['anemic_moderate']:
        return 'Moderate'
    elif value['anemic_normal']:
        return 'Normal'
    else:
        return DATA_NOT_ENTERED


def get_symptoms(value):
    if value['bleeding']:
        return 'Bleeding'
    elif value['swelling']:
        return 'Face, hand or genital swelling'
    elif value['blurred_vision']:
        return 'Blurred vision / headache'
    elif value['convulsions']:
        return 'Convulsions / unconsciousness'
    elif value['rupture']:
        return 'Water ruptured without labor pains'
    else:
        return 'None'


def get_counseling(value):
    counseling = []
    if value['eating_extra']:
        counseling.append('Eating Extra')
    if value['resting']:
        counseling.append('Taking Rest')
    if value['immediate_breastfeeding']:
        counseling.append('Counsel on Immediate Breastfeeding')
    if counseling:
        return ', '.join(counseling)
    else:
        return 'None'


def get_tt_dates(value):
    tt_dates = []
    # ignore 1970-01-01 as that is default date for ledger dates
    default = date(1970, 1, 1)
    if value['tt_1'] and value['tt_1'] != default:
        tt_dates.append(str(value['tt_1']))
    if value['tt_2'] and value['tt_2'] != default:
        tt_dates.append(str(value['tt_2']))
    if tt_dates:
        return '; '.join(tt_dates)
    else:
        return 'None'


def get_delivery_nature(value):
    delivery_natures = {
        1: 'Vaginal',
        2: 'Caesarean',
        3: 'Instrumental',
        0: DATA_NOT_ENTERED,
    }
    return delivery_natures.get(value['delivery_nature'], DATA_NOT_ENTERED)


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


def generate_data_for_map(data, loc_level, num_prop, denom_prop, fill_key_lower, fill_key_bigger, all_property=None):
    data_for_map = defaultdict(lambda: {
        num_prop: 0,
        denom_prop: 0,
        'original_name': []
    })

    if all_property:
        data_for_map = defaultdict(lambda: {
            num_prop: 0,
            denom_prop: 0,
            'original_name': [],
            all_property: 0
        })

    valid_total = 0
    in_month_total = 0
    total = 0
    values_to_calculate_average = {'numerator': 0, 'denominator': 0}

    for row in data:
        valid = row[denom_prop] or 0
        name = row['%s_name' % loc_level]
        on_map_name = row['%s_map_location_name' % loc_level] or name
        in_month = row[num_prop] or 0

        values_to_calculate_average['numerator'] += in_month if in_month else 0
        values_to_calculate_average['denominator'] += row[denom_prop] if row[denom_prop] else 0

        valid_total += valid
        in_month_total += in_month
        if all_property:
            all_data = row[all_property] or 0
            data_for_map[on_map_name][all_property] += all_data
            total += all_data
        data_for_map[on_map_name][num_prop] += in_month
        data_for_map[on_map_name][denom_prop] += valid
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

    average = (
        (values_to_calculate_average['numerator'] * 100) /
        float(values_to_calculate_average['denominator'] or 1)
    )
    return data_for_map, valid_total, in_month_total, average, total


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
        '6': '0-6 months (0-180 days)',
        '12': '6-12 months (181-365 days)',
        '24': '12-24 months (366-730 days)',
        '36': '24-36 months (731-1095 days)',
        '48': '36-48 months (1096-1460 days)',
        '60': '48-60 months (1461-1825 days)',
        '72': '60-72 months (1826-2190 days)'
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
        chosen_age = default_interval

    delimiter = ', ' if gender and chosen_age else ''
    chosen_filters = ' ({gender}{delimiter}{age})'\
        .format(gender=chosen_gender, delimiter=delimiter, age=chosen_age) if gender or chosen_age else ''

    return gender_label, chosen_age, chosen_filters


def zip_folder(pdf_files):
    zip_hash = uuid.uuid4().hex
    icds_file = IcdsFile(blob_id=zip_hash, data_type='issnip_monthly')
    in_memory = BytesIO()
    zip_file = zipfile.ZipFile(in_memory, 'w', zipfile.ZIP_DEFLATED)
    files_to_zip = IcdsFile.objects.filter(blob_id__in=list(pdf_files.keys()), data_type='issnip_monthly')

    for pdf_file in files_to_zip:
        zip_file.writestr(
            'ICDS_CAS_monthly_register_{}.pdf'.format(pdf_files[pdf_file.blob_id]),
            pdf_file.get_file_from_blobdb().read()
        )
    zip_file.close()

    # we need to reset buffer position to the beginning after creating zip, if not read() will return empty string
    # we read this to save file in blobdb
    in_memory.seek(0)
    icds_file.store_file_in_blobdb(in_memory, expired=ONE_DAY)
    icds_file.save()
    return zip_hash


def create_excel_file(excel_data, data_type, file_format, blob_key=None, timeout=ONE_DAY):
    key = blob_key or uuid.uuid4().hex
    export_file = BytesIO()
    icds_file, _ = IcdsFile.objects.get_or_create(blob_id=key, data_type=data_type)
    export_from_tables(excel_data, export_file, file_format)
    export_file.seek(0)
    icds_file.store_file_in_blobdb(export_file, expired=timeout)
    icds_file.save()
    return key


def create_pdf_file(pdf_context):
    pdf_hash = uuid.uuid4().hex
    template = get_template("icds_reports/icds_app/pdf/issnip_monthly_register.html")
    resultFile = BytesIO()
    icds_file = IcdsFile(blob_id=pdf_hash, data_type='issnip_monthly')
    try:
        pdf_page = template.render(pdf_context)
    except Exception as ex:
        pdf_page = str(ex)
    base_url = os.path.join(settings.FILEPATH, 'custom', 'icds_reports', 'static')
    resultFile.write(HTML(string=pdf_page, base_url=base_url).write_pdf(
        stylesheets=[CSS(os.path.join(base_url, 'css', 'issnip_monthly_print_style.css')), ])
    )
    # we need to reset buffer position to the beginning after creating pdf, if not read() will return empty string
    # we read this to save file in blobdb
    resultFile.seek(0)

    icds_file.store_file_in_blobdb(resultFile, expired=ONE_DAY)
    icds_file.save()
    return pdf_hash


def generate_qrcode(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image()
    output = BytesIO()
    image.save(output, "PNG")
    qr_content = b64encode(output.getvalue())
    return qr_content


def icds_pre_release_features(user):
    return toggles.ICDS_DASHBOARD_REPORT_FEATURES.enabled(user.username)


def indian_formatted_number(number):
    s = str(number)
    if s.isdigit():
        r = ",".join([s[x - 2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return "".join(r)
    else:
        return 0


@quickcache(['domain', 'location_id', 'show_test'], timeout=5 * 60)
def get_child_locations(domain, location_id, show_test):
    if location_id:
        locations = SQLLocation.objects.get(domain=domain, location_id=location_id).get_children()
    else:
        locations = SQLLocation.objects.filter(domain=domain, location_type__code=const.LocationTypes.STATE)

    if not show_test:
        return [
            sql_location for sql_location in locations
            if sql_location.metadata.get('is_test_location', 'real') != 'test'
        ]
    else:
        return list(locations)


def person_has_aadhaar_column(beta):
    return 'cases_person_has_aadhaar_v2'


def person_is_beneficiary_column(beta):
    return 'cases_person_beneficiary_v2'


def wasting_moderate_column(beta):
    return 'wasting_moderate_v2'


def wasting_severe_column(beta):
    return 'wasting_severe_v2'


def wasting_normal_column(beta):
    return 'wasting_normal_v2'


def stunting_moderate_column(beta):
    return 'zscore_grading_hfa_moderate'


def stunting_severe_column(beta):
    return 'zscore_grading_hfa_severe'


def stunting_normal_column(beta):
    return 'zscore_grading_hfa_normal'


def current_month_stunting_column(beta):
    return 'current_month_stunting_v2'


def current_month_wasting_column(beta):
    return 'current_month_wasting_v2'


def hfa_recorded_in_month_column(beta):
    return 'zscore_grading_hfa_recorded_in_month'


def wfh_recorded_in_month_column(beta):
    return 'zscore_grading_wfh_recorded_in_month'


def default_age_interval(beta):
    return '0 - 5 years'


def get_age_filters(beta):
    return [
        NOT(EQ('age_tranche', 'age_72'))
    ]


def get_age_condition(beta):
    return "age_tranche != :age_72"


def track_time(func):
    """A decorator to track the duration an aggregation script takes to execute"""
    from custom.icds_reports.models import AggregateSQLProfile

    def get_async_indicator_time():
        try:
            return AsyncIndicator.objects.exclude(date_queued__isnull=True)\
                .aggregate(Max('date_created'))['date_created__max'] or datetime.now()
        except OperationalError:
            return None

    def get_sync_datasource_time():
        return KafkaCheckpoint.objects.filter(checkpoint_id__in=const.UCR_PILLOWS) \
            .exclude(doc_modification_time__isnull=True)\
            .aggregate(Min('doc_modification_time'))['doc_modification_time__min']


    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()

        sync_latest_ds_update = get_sync_datasource_time()
        async_latest_ds_update = get_async_indicator_time()

        if sync_latest_ds_update and async_latest_ds_update:
            last_included_doc_time = min(sync_latest_ds_update, async_latest_ds_update)
        else:
            last_included_doc_time = sync_latest_ds_update or async_latest_ds_update

        AggregateSQLProfile.objects.create(
            name=func.__name__,
            duration=int(end - start),
            last_included_doc_time=last_included_doc_time
        )
        return result

    return wrapper


def percent_num(x, y):
    return (x or 0) * 100 / float(y or 1)


def percent(x, y):
    return "%.2f %%" % (percent_num(x, y))


def format_decimal(num):
    return "%.2f" % num


def percent_or_not_entered(x, y):
    return percent(x, y) if y and x is not None else DATA_NOT_ENTERED


def india_now():
    utc_now = datetime.now(pytz.utc)
    india_now = utc_now.astimezone(india_timezone)
    return india_now.strftime("%H:%M:%S %d %B %Y")


def day_suffix(day):
    return 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')


def custom_strftime(format_to_use, date_to_format):
    # adds {S} option to strftime that formats day as 1st, 3rd, 11th etc.
    return date_to_format.strftime(format_to_use).replace(
        '{S}', str(date_to_format.day) + day_suffix(date_to_format.day)
    )


def create_aww_performance_excel_file(excel_data, data_type, month, state, district=None, block=None):
    aggregation_level = 3 if block else (2 if district else 1)
    export_info = excel_data[1][1]
    excel_data = [line[aggregation_level:] for line in excel_data[0][1]]
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    warp_text_alignment = Alignment(wrap_text=True)
    bold_font = Font(bold=True)
    blue_fill = PatternFill("solid", fgColor="B3C5E5")
    grey_fill = PatternFill("solid", fgColor="BFBFBF")

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "AWW Performance Report"
    worksheet.sheet_view.showGridLines = False
    # sheet title
    worksheet.merge_cells('B2:{0}2'.format(
        "K" if aggregation_level == 3 else ("L" if aggregation_level == 2 else "M")
    ))
    title_cell = worksheet['B2']
    title_cell.fill = PatternFill("solid", fgColor="4472C4")
    title_cell.value = "AWW Performance Report for the month of {}".format(month)
    title_cell.font = Font(size=18, color="FFFFFF")
    title_cell.alignment = Alignment(horizontal="center")

    # sheet header
    header_cells = ["B3", "C3", "D3", "E3", "F3", "G3", "H3", "I3", "J3", "K3"]
    if aggregation_level < 3:
        header_cells.append("L3")
    if aggregation_level < 2:
        header_cells.append("M3")

    for cell in header_cells:
        worksheet[cell].fill = blue_fill
        worksheet[cell].font = bold_font
        worksheet[cell].alignment = warp_text_alignment
    worksheet.merge_cells('B3:C3')
    worksheet['B3'].value = "State: {}".format(state)
    if district:
        worksheet['D3'].value = "District: {}".format(district)
    worksheet.merge_cells('E3:F3')
    if block:
        worksheet['E3'].value = "Block: {}".format(block)

    # table header
    table_header_position_row = 5
    headers = ["S.No"]
    if aggregation_level < 2:
        headers.append("District")
    if aggregation_level < 3:
        headers.append("Block")

    headers.extend([
        'Supervisor', 'AWC', 'AWW Name', 'AWW Contact Number',
        'Home Visits Conducted', 'Weighing Efficiency', 'AWW Eligible for Incentive',
        'Number of Days AWC was Open', 'AWH Eligible for Incentive'
    ])
    columns = ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K']
    if aggregation_level < 3:
        columns.append('L')
    if aggregation_level < 2:
        columns.append('M')

    table_header = {}
    for col, header in zip(columns, headers):
        table_header[col] = header
    for column, value in table_header.items():
        cell = "{}{}".format(column, table_header_position_row)
        worksheet[cell].fill = grey_fill
        worksheet[cell].border = thin_border
        worksheet[cell].font = bold_font
        worksheet[cell].alignment = warp_text_alignment
        worksheet[cell].value = value

    # table contents
    row_position = table_header_position_row + 1

    for enum, row in enumerate(excel_data[1:], start=1):
        for column_index in range(len(columns)):
            column = columns[column_index]
            cell = "{}{}".format(column, row_position)
            worksheet[cell].border = thin_border
            if column_index == 0:
                worksheet[cell].value = enum
            else:
                worksheet[cell].value = row[column_index - 1]
        row_position += 1

    # sheet dimensions
    title_row = worksheet.row_dimensions[2]
    title_row.height = 23
    worksheet.row_dimensions[table_header_position_row].height = 46
    widths = {}
    widths_columns = ['A']
    widths_columns.extend(columns)
    standard_widths = [4, 7, 15]
    standard_widths.extend([15] * (3 - aggregation_level))
    standard_widths.extend([13, 12, 13, 15, 11, 14, 14])
    standard_widths.append(14)

    for col, width in zip(widths_columns, standard_widths):
        widths[col] = width
    widths['C'] = max(widths['C'], len(state) * 4 // 3 if state else 0)
    widths['D'] = 13 + (len(district) * 4 // 3 if district else 0)
    widths['F'] = max(widths['F'], len(block) * 4 // 3 if block else 0)
    for column in ["C", "E", "G"]:
        if widths[column] > 25:
            worksheet.row_dimensions[3].height = max(
                16 * ((widths[column] // 25) + 1),
                worksheet.row_dimensions[3].height
            )
            widths[column] = 25
    columns = columns[1:]
    # column widths based on table contents
    for column_index in range(len(columns)):
        widths[columns[column_index]] = max(
            widths[columns[column_index]],
            max(
                len(row[column_index].decode('utf-8') if isinstance(row[column_index], bytes)
                    else six.text_type(row[column_index])
                    )
                for row in excel_data[1:]) * 4 // 3 if len(excel_data) >= 2 else 0
        )

    for column, width in widths.items():
        worksheet.column_dimensions[column].width = width

    # export info
    worksheet2 = workbook.create_sheet("Export Info")
    worksheet2.column_dimensions['A'].width = 14
    for n, export_info_item in enumerate(export_info, start=1):
        worksheet2['A{0}'.format(n)].value = export_info_item[0]
        worksheet2['B{0}'.format(n)].value = export_info_item[1]

    # saving file
    key = get_performance_report_blob_key(state, district, block, month, 'xlsx')
    export_file = BytesIO()
    icds_file, _ = IcdsFile.objects.get_or_create(blob_id=key, data_type=data_type)
    workbook.save(export_file)
    export_file.seek(0)
    icds_file.store_file_in_blobdb(export_file, expired=None)
    icds_file.save()
    return key


def get_performance_report_blob_key(state, district, block, month, file_format):
    key_safe_date = datetime.strptime(month, '%B %Y').strftime('%Y_%m')
    key = 'performance_report-{}-{}-{}-{}-{}'.format(state, district, block, key_safe_date, file_format)
    safe_key = key.replace(' ', '_')
    return safe_id(safe_key)


def create_excel_file_in_openpyxl(excel_data, data_type):
    workbook = Workbook()
    first_worksheet = True
    for worksheet_data in excel_data:
        if first_worksheet:
            worksheet = workbook.active
            worksheet.title = worksheet_data[0]
            first_worksheet = False
        else:
            worksheet = workbook.create_sheet(worksheet_data[0])
        for row_number, row_data in enumerate(worksheet_data[1], start=1):
            for column_number, cell_data in enumerate(row_data, start=1):
                worksheet.cell(row=row_number, column=column_number).value = cell_data

    # saving file
    file_hash = uuid.uuid4().hex
    export_file = BytesIO()
    icds_file = IcdsFile(blob_id=file_hash, data_type=data_type)
    workbook.save(export_file)
    export_file.seek(0)
    icds_file.store_file_in_blobdb(export_file, expired=ONE_DAY)
    icds_file.save()
    return file_hash


def create_thr_report_excel_file(excel_data, data_type, month, aggregation_level):
    export_info = excel_data[1][1]
    national = 'National Level' if aggregation_level == 0 else ''
    state = export_info[1][1] if aggregation_level > 0 else ''
    district = export_info[2][1] if aggregation_level > 1 else ''
    block = export_info[3][1] if aggregation_level > 2 else ''
    supervisor = export_info[3][1] if aggregation_level > 3 else ''

    excel_data = [line[aggregation_level:] for line in excel_data[0][1]]
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    warp_text_alignment = Alignment(wrap_text=True)
    bold_font = Font(bold=True)
    blue_fill = PatternFill("solid", fgColor="B3C5E5")
    grey_fill = PatternFill("solid", fgColor="BFBFBF")

    workbook = Workbook()
    worksheet = workbook.active
    # sheet title
    worksheet.title = "THR Report"
    worksheet.sheet_view.showGridLines = False
    amount_of_columns = 11 - aggregation_level
    last_column = string.ascii_uppercase[amount_of_columns]
    worksheet.merge_cells('B2:{0}2'.format(last_column))
    title_cell = worksheet['B2']
    title_cell.fill = PatternFill("solid", fgColor="4472C4")
    title_cell.value = "Take Home Ration(THR) Report for the {}".format(month)
    title_cell.font = Font(size=18, color="FFFFFF")
    title_cell.alignment = Alignment(horizontal="center")

    columns = [string.ascii_uppercase[i] for i in range(1, amount_of_columns + 1)]

    # sheet header
    header_cells = ['{0}3'.format(column) for column in columns]
    for cell in header_cells:
        worksheet[cell].fill = blue_fill
        worksheet[cell].font = bold_font
        worksheet[cell].alignment = warp_text_alignment

    if national:
        worksheet['B3'].value = national
        worksheet.merge_cells('B3:C3')
    else:
        if state:
            worksheet['B3'].value = "State: {}".format(state)
            worksheet.merge_cells('B3:C3')
        if district:
            worksheet['D3'].value = "District: {}".format(district)
        if block:
            worksheet['E3'].value = "Block: {}".format(block)
        if supervisor:
            worksheet['F3'].value = "Sector: {}".format(supervisor)

    date_cell = '{0}3'.format(last_column)
    date_description_cell = '{0}3'.format(string.ascii_uppercase[amount_of_columns - 1])
    worksheet[date_description_cell].value = "Date when downloaded:"
    worksheet[date_description_cell].alignment = Alignment(horizontal="right")
    utc_now = datetime.now(pytz.utc)
    now_in_india = utc_now.astimezone(india_timezone)
    worksheet[date_cell].value = custom_strftime('{S} %b %Y', now_in_india)
    worksheet[date_cell].alignment = Alignment(horizontal="right")

    # table header
    table_header_position_row = 5
    header_data = excel_data[0]
    headers = ["S.No"]
    headers.extend(header_data)

    table_header = {}
    for col, header in zip(columns, headers):
        table_header[col] = header
    for column, value in table_header.items():
        cell = "{}{}".format(column, table_header_position_row)
        worksheet[cell].fill = grey_fill
        worksheet[cell].border = thin_border
        worksheet[cell].font = bold_font
        worksheet[cell].alignment = warp_text_alignment
        worksheet[cell].value = value

    # table contents
    row_position = table_header_position_row + 1

    for enum, row in enumerate(excel_data[1:], start=1):
        for column_index in range(len(columns)):
            column = columns[column_index]
            cell = "{}{}".format(column, row_position)
            worksheet[cell].border = thin_border
            if column_index == 0:
                worksheet[cell].value = enum
            else:
                worksheet[cell].value = row[column_index - 1]
        row_position += 1

    # sheet dimensions
    title_row = worksheet.row_dimensions[2]
    title_row.height = 23
    worksheet.row_dimensions[table_header_position_row].height = 46
    widths = {}
    widths_columns = ['A']
    widths_columns.extend(columns)
    standard_widths = [4, 7]
    standard_widths.extend([15] * (4 - aggregation_level))
    standard_widths.extend([25, 15, 25, 15, 15, 15])
    for col, width in zip(widths_columns, standard_widths):
        widths[col] = width

    widths['C'] = max(widths['C'], len(state) * 4 // 3 if state else 0)
    widths['D'] = 9 + (len(district) * 4 // 3 if district else 0)
    widths['E'] = 8 + (len(block) * 4 // 3 if district else 0)
    widths['F'] = 8 + (len(supervisor) * 4 // 3 if district else 0)

    columns = columns[1:]
    # column widths based on table contents
    for column_index in range(len(columns)):
        widths[columns[column_index]] = max(
            widths[columns[column_index]],
            max(
                len(row[column_index].decode('utf-8') if isinstance(row[column_index], bytes)
                    else six.text_type(row[column_index])
                    )
                for row in excel_data[1:]) * 4 // 3 if len(excel_data) >= 2 else 0
        )

    for column, width in widths.items():
        worksheet.column_dimensions[column].width = width

    # export info
    worksheet2 = workbook.create_sheet("Export Info")
    worksheet2.column_dimensions['A'].width = 14
    for n, export_info_item in enumerate(export_info, start=1):
        worksheet2['A{0}'.format(n)].value = export_info_item[0]
        worksheet2['B{0}'.format(n)].value = export_info_item[1]

    # saving file
    file_hash = uuid.uuid4().hex
    export_file = BytesIO()
    icds_file = IcdsFile(blob_id=file_hash, data_type=data_type)
    workbook.save(export_file)
    export_file.seek(0)
    icds_file.store_file_in_blobdb(export_file, expired=ONE_DAY)
    icds_file.save()
    return file_hash


def create_lady_supervisor_excel_file(excel_data, data_type, month, aggregation_level):
    export_info = excel_data[1][1]
    state = export_info[1][1] if aggregation_level > 0 else ''
    district = export_info[2][1] if aggregation_level > 1 else ''
    block = export_info[3][1] if aggregation_level > 2 else ''
    excel_data = [line[aggregation_level:] for line in excel_data[0][1]]
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    warp_text_alignment = Alignment(wrap_text=True)
    bold_font = Font(bold=True)
    blue_fill = PatternFill("solid", fgColor="B3C5E5")
    grey_fill = PatternFill("solid", fgColor="BFBFBF")

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "LS Performance Report"
    worksheet.sheet_view.showGridLines = False
    # sheet title
    amount_of_columns = 9 - aggregation_level
    last_column = string.ascii_uppercase[amount_of_columns]
    worksheet.merge_cells('B2:{0}2'.format(last_column))
    title_cell = worksheet['B2']
    title_cell.fill = PatternFill("solid", fgColor="4472C4")
    title_cell.value = "Lady Supervisor Performance Report for the {}".format(month)
    title_cell.font = Font(size=18, color="FFFFFF")
    title_cell.alignment = Alignment(horizontal="center")

    columns = [string.ascii_uppercase[i] for i in range(1, amount_of_columns + 1)]

    # sheet header
    header_cells = ['{0}3'.format(column) for column in columns]
    for cell in header_cells:
        worksheet[cell].fill = blue_fill
        worksheet[cell].font = bold_font
        worksheet[cell].alignment = warp_text_alignment
    if state:
        worksheet['B3'].value = "State: {}".format(state)
        worksheet.merge_cells('B3:C3')
    if district:
        worksheet['D3'].value = "District: {}".format(district)
    if block:
        worksheet['E3'].value = "Block: {}".format(block)
    date_cell = '{0}3'.format(last_column)
    date_description_cell = '{0}3'.format(string.ascii_uppercase[amount_of_columns - 1])
    worksheet[date_description_cell].value = "Date when downloaded:"
    worksheet[date_description_cell].alignment = Alignment(horizontal="right")
    utc_now = datetime.now(pytz.utc)
    now_in_india = utc_now.astimezone(india_timezone)
    worksheet[date_cell].value = custom_strftime('{S} %b %Y', now_in_india)
    worksheet[date_cell].alignment = Alignment(horizontal="right")

    # table header
    table_header_position_row = 5
    header_data = excel_data[0]
    headers = ["S.No"]
    headers.extend(header_data)

    table_header = {}
    for col, header in zip(columns, headers):
        table_header[col] = header
    for column, value in table_header.items():
        cell = "{}{}".format(column, table_header_position_row)
        worksheet[cell].fill = grey_fill
        worksheet[cell].border = thin_border
        worksheet[cell].font = bold_font
        worksheet[cell].alignment = warp_text_alignment
        worksheet[cell].value = value

    # table contents
    row_position = table_header_position_row + 1

    for enum, row in enumerate(excel_data[1:], start=1):
        for column_index in range(len(columns)):
            column = columns[column_index]
            cell = "{}{}".format(column, row_position)
            worksheet[cell].border = thin_border
            if column_index == 0:
                worksheet[cell].value = enum
            else:
                worksheet[cell].value = row[column_index - 1]
        row_position += 1

    # sheet dimensions
    title_row = worksheet.row_dimensions[2]
    title_row.height = 23
    worksheet.row_dimensions[table_header_position_row].height = 46
    widths = {}
    widths_columns = ['A']
    widths_columns.extend(columns)
    standard_widths = [4, 7]
    standard_widths.extend([15] * (4 - aggregation_level))
    standard_widths.extend([25, 15, 25, 15])
    for col, width in zip(widths_columns, standard_widths):
        widths[col] = width
    widths['C'] = max(widths['C'], len(state) * 4 // 3 if state else 0)
    widths['D'] = 9 + (len(district) * 4 // 3 if district else 0)
    widths['E'] = 8 + (len(block) * 4 // 3 if district else 0)

    columns = columns[1:]
    # column widths based on table contents
    for column_index in range(len(columns)):
        widths[columns[column_index]] = max(
            widths[columns[column_index]],
            max(
                len(row[column_index].decode('utf-8') if isinstance(row[column_index], bytes)
                    else six.text_type(row[column_index])
                    )
                for row in excel_data[1:]) * 4 // 3 if len(excel_data) >= 2 else 0
        )

    for column, width in widths.items():
        worksheet.column_dimensions[column].width = width

    # export info
    worksheet2 = workbook.create_sheet("Export Info")
    worksheet2.column_dimensions['A'].width = 14
    for n, export_info_item in enumerate(export_info, start=1):
        worksheet2['A{0}'.format(n)].value = export_info_item[0]
        worksheet2['B{0}'.format(n)].value = export_info_item[1]

    # saving file
    file_hash = uuid.uuid4().hex
    export_file = BytesIO()
    icds_file = IcdsFile(blob_id=file_hash, data_type=data_type)
    workbook.save(export_file)
    export_file.seek(0)
    icds_file.store_file_in_blobdb(export_file, expired=ONE_DAY)
    icds_file.save()
    return file_hash


def get_datatables_ordering_info(request):
    # retrive table ordering provided by datatables plugin upon clicking on column header
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    order_by_number_column = request.GET.get('order[0][column]')
    order_by_name_column = request.GET.get('columns[%s][data]' % order_by_number_column)
    order_dir = request.GET.get('order[0][dir]', 'asc')
    return start, length, order_by_number_column, order_by_name_column, order_dir


def phone_number_function(x):
    return "+{0}{1}".format('' if str(x).startswith('91') else '91', x) if x else x
