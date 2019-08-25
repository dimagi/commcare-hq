# coding=utf-8

import datetime

from django.utils.functional import cached_property

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import DateRangeFilter, YeksiNaaLocationFilter, ProgramFilter
from dimagi.utils.dates import force_to_date


class RecapPassageTwoReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    slug = 'recap_passage_2'
    comment = 'recap passage 2'
    name = 'Recap Passage 2'
    default_rows = 10

    report_template_path = 'yeksi_naa/tabular_report.html'

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
        # TODO: needs further implementation
        return DataTablesHeader(
            DataTablesColumn(self.selected_location_type),
            DataTablesColumn(
                'Rows'
            ),
        )

    def get_report_context(self):
        if self.needs_filters:
            headers = []
            rows = []
        else:
            rows = self.calculate_rows()
            headers = self.headers

        context = dict(
            report_table=dict(
                title=self.name,
                slug=self.slug,
                comment=self.comment,
                headers=headers,
                rows=rows,
                default_rows=self.default_rows,
            )
        )

        return context

    def calculate_rows(self):
        # TODO: needs further implementation (new Data classes)
        rows = []
        return rows

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
        config['product_program'] = self.request.GET.get('product_program')
        config['selected_location'] = self.request.GET.get('location_id')
        return config
