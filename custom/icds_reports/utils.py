import json
import os

from datetime import datetime, timedelta

import operator

from django.db.models.aggregates import Sum
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import StaticReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from dimagi.utils.dates import DateSpan

from custom.icds_reports.models import AggDailyUsageView

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


def get_system_usage_data(filters):
    yesterday_data = AggDailyUsageView.objects.filter(
        date=filters['yesterday'], aggregation_level=1
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
    before_yesterday_data = AggDailyUsageView.objects.filter(
        date=filters['before_yesterday'], aggregation_level=1
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

    def percent_increase(prop):
        yesterday = yesterday_data[0][prop]
        before_yesterday = before_yesterday_data[0][prop]
        return (yesterday - before_yesterday) / float(before_yesterday) * 100

    return {
        'records': [
            [
                {
                    'label': _('Number of AWCs Open yesterday'),
                    'help_text': _("""Total Number of Angwanwadi Centers that were open yesterday
                        by the AWW or the AWW helper"""),
                    'percent': percent_increase('daily_attendance'),
                    'value': yesterday_data[0]['daily_attendance'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'div'
                },
                {
                    'label': _('Average number of forms hosuehold registration forms submitted yesterday'),
                    'help_text': _('Average number of household registration forms submitted by AWWs yesterday.'),
                    'percent': percent_increase('num_forms'),
                    'value': yesterday_data[0]['num_forms'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'number'
                }
            ],
            [
                {
                    'label': _('Average number of Home Visit forms submitted yesterday'),
                    'help_text': _("""Average number of home visit forms submitted yesterday. Home visit forms are 
                        Birth Preparedness, Delivery, Post Natal Care, 
                        Exclusive breastfeeding and Complementary feeding"""),
                    'percent': percent_increase('num_home_visits'),
                    'value': yesterday_data[0]['num_home_visits'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'number'
                },
                {
                    'label': _('Average number of Growth Monitoring forms submitted yesterday'),
                    'help_text': _('Average number of growth monitoring forms (GMP) submitted yesterday'),
                    'percent': percent_increase('num_gmp'),
                    'value': yesterday_data[0]['num_gmp'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'number'
                }
            ], [
                {
                    'label': _('Average number of Take Home Ration forms submitted yesterday'),
                    'help_text': _('Average number of Take Home Rations (THR) forms submitted yesterday'),
                    'percent': percent_increase('num_thr'),
                    'value': yesterday_data[0]['num_thr'],
                    'all': yesterday_data[0]['awcs'],
                    'format': 'number'
                }
            ]
        ]
    }