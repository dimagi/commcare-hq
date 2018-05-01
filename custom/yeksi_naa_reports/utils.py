# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from corehq.apps.locations.models import get_location
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from dateutil.relativedelta import relativedelta
from django.utils.functional import cached_property


YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR = 'yeksi_naa_reports_visite_de_l_operateur'
YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT = "yeksi_naa_reports_visite_de_l_operateur_per_product"
YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PROGRAM = "yeksi_naa_reports_visite_de_l_operateur_per_program"
YEKSI_NAA_REPORTS_LOGISTICIEN = 'yeksi_naa_reports_logisticien'


class YeksiNaaLocationMixin(object):

    @cached_property
    def location(self):
        if self.request.GET.get('location_id'):
            return get_location(self.request.GET.get('location_id'))


class YeksiNaaReportConfigMixin(object):

    def config_update(self, config):
        if self.request.GET.get('location_id', ''):
            if self.location.location_type_name.lower() == 'pps':
                config.update(dict(pps_id=self.location.location_id))
            elif self.location.location_type_name.lower() == 'district':
                config.update(dict(district_id=self.location.location_id))
            else:
                config.update(dict(region_id=self.location.location_id))

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
        )
        if self.request.GET.get('month_start'):
            startdate = datetime.datetime(
                year=int(self.request.GET.get('year_start')),
                month=int(self.request.GET.get('month_start')),
                day=1,
                hour=0,
                minute=0,
                second=0
            )
            enddate = datetime.datetime(
                year=int(self.request.GET.get('year_end')),
                month=int(self.request.GET.get('month_end')),
                day=1,
                hour=23,
                minute=59,
                second=59
            )
            enddate = enddate + relativedelta(months=1) - relativedelta(days=1)
        else:
            startdate = datetime.datetime.now()
            startdate.replace(month=1, day=1, hour=0, minute=0, second=0)
            enddate = datetime.datetime.now()
            enddate.replace(day=1, hour=23, minute=59, second=59)
            enddate = startdate + relativedelta(month=1) - relativedelta(day=1)
        config['startdate'] = startdate
        config['enddate'] = enddate
        if self.request.GET.get('program'):
            config['program'] = self.request.GET.get('program')
        self.config_update(config)
        return config


class YeksiNaaMixin(YeksiNaaLocationMixin, YeksiNaaReportConfigMixin):
    data_source = None

    @property
    def headers(self):
        return DataTablesHeader()

    @property
    def rows(self):
        return []


class MultiReport(CustomProjectReport, YeksiNaaMixin, ProjectReportParametersMixin):

    title = ''
    report_template_path = "yeksi_naa/multi_report.html"
    flush_layout = True
    export_format_override = 'csv'

    @cached_property
    def rendered_report_title(self):
        return self.title

    @cached_property
    def data_providers(self):
        return []

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title
        }

        return context

    def get_report_context(self, data_provider):

        total_row = []
        self.data_source = data_provider
        if self.needs_filters:
            headers = []
            rows = []
        else:
            headers = data_provider.headers
            rows = data_provider.rows
            total_row = data_provider.total_row

        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                comment=data_provider.comment,
                headers=headers,
                rows=rows,
                total_row=total_row,
                default_rows=self.default_rows,
                datatables=data_provider.datatables,
                fix_column=data_provider.fix_left_col
            )
        )

        return context

    @property
    def export_table(self):
        reports = [r['report_table'] for r in self.report_context['reports']]
        return [self._export_table(r['title'], r['headers'], r['rows'], total_row=r['total_row']) for r in reports]

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        replace = ''

        # make headers and subheaders consistent
        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]
