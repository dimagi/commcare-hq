# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

import datetime

from django.utils.functional import cached_property

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import DateRangeFilter, YeksiNaaLocationFilter, ProgramFilter
from custom.intrahealth.reports.utils import YeksiNaaMonthYearMixin
from custom.intrahealth.sqldata import RecapPassageTwoData, RecapPassageTwoTables
from custom.intrahealth.reports.tableu_de_board_report_v2 import MultiReport
from dimagi.utils.dates import force_to_date



class RecapPassageTwoReport(YeksiNaaMonthYearMixin, MultiReport):
    slug = 'recap_passage_2'
    comment = 'recap passage 2'
    name = 'Recap Passage 2'
    title = "Recap Passage 2"
    default_rows = 10
    exportable = True
    report_template_path = "intrahealth/multi_report.html"

    @property
    def fields(self):
        return [DateRangeFilter, ProgramFilter, YeksiNaaLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @cached_property
    def data_providers(self):
        table_provider = RecapPassageTwoTables(config=self.config)
        return [
            table_provider.sumup_context,
            table_provider.billed_consumption_context,
            table_provider.actual_consumption_context,
            table_provider.amt_delivered_convenience_context,
            table_provider.display_total_stock_context,
        ]

    def get_report_context(self, table_context):
        total_row = []
        self.data_source = table_context
        if self.needs_filters:
            headers = []
            rows = []
            context = dict(
                report_table = dict(
                    rows = [],
                    headers = []
                )
            )
        else:
            context = dict(
                report_table=table_context
            )
        return context

    @property
    def config(self):
        config = dict(
            domain=self.domain,
        )
        if self.request.GET.get('startdate'):
            startdate = force_to_date(self.request.GET.get('startdate'))
        else:
            startdate = datetime.datetime.now()
        if self.request.GET.get('enddate'):
            enddate = force_to_date(self.request.GET.get('enddate'))
        else:
            enddate = datetime.datetime.now()
        config['startdate'] = startdate
        config['enddate'] = enddate
        config['product_program'] = self.request.GET.get('program')
        config['selected_location'] = self.request.GET.get('location_id')
        return config
