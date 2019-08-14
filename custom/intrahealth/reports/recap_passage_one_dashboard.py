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
from custom.intrahealth.sqldata import RecapPassageOneData
from dimagi.utils.dates import force_to_date


class RecapPassageOneReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    slug = 'recap_passage_1'
    comment = 'recap passage 1'
    name = 'Recap Passage 1'
    default_rows = 10

    report_template_path = 'yeksi_naa/recap_passage.html'

    @property
    def fields(self):
        return [DateRangeFilter, ProgramFilter, YeksiNaaLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @property
    def report_context(self):
        context = {
            'report': self.get_report_context(),
            'title': self.name
        }

        return context

    @property
    def selected_location(self):
        try:
            return SQLLocation.objects.get(location_id=self.request.GET.get('location_id'))
        except SQLLocation.DoesNotExist:
            return None

    @property
    def selected_location_type(self):
        if self.selected_location:
            location_type = self.selected_location.location_type.code
            if location_type == 'region':
                return 'District'
            else:
                return 'PPS'
        else:
            return 'Region'

    @property
    def headers(self):
        return RecapPassageOneData(config=self.config).headers

    @property
    def aggregated_headers(self):
        # TODO: needs further implementation

        headers = RecapPassageOneData(config=self.config).headers.header
        return DataTablesHeader(
            *(headers[:2])
        )

    @property
    def comment(self):
        choosen_product = RecapPassageOneData(config=self.config).program_name
        return choosen_product or None

    def aggregated_rows(self):
        # TODO: needs further implementation

        headers = RecapPassageOneData(config=self.config).headers.header
        return DataTablesHeader(
            DataTablesColumn('uno'),
            DataTablesColumn('dos'),
        )

    def get_report_context(self):
        if self.needs_filters:
            headers = []
            aggregated_headers = []
            rows = []
            aggregated_rows = []
            comment = ""
        else:
            rows, headers = self.calculate_table()
            aggregated_rows, aggregated_headers = self.calculate_aggregated_table()
            
            for n in range(len(aggregated_headers)):
                aggregated_headers.header[n].row = aggregated_rows[n]

            comment = self.comment

        context = dict(
            report_table=dict(
                title=self.name,
                slug=self.slug,
                comment=comment,
                headers=headers,
                rows=rows,
                project=self.request.GET.get('project_name') or "Malaria",
                default_rows=self.default_rows,
            ),
            aggregated_table=dict(
                headers=aggregated_headers,
                rows=aggregated_rows,
                number_of_agregated=2
            )
        )

        return context

    def calculate_rows(self):
        rows = RecapPassageOneData(config=self.config).rows
        return rows

    def calculate_table(self):
        return RecapPassageOneData(config=self.config).rows_and_headers

    def calculate_aggregated_table(self):
        return RecapPassageOneData(config=self.config).aggregated_data

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
