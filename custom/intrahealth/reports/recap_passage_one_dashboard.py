# coding=utf-8

import datetime

from django.utils.functional import cached_property

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import DateRangeFilter, RecapPassageOneProgramFilter, \
    YeksiRecapPassageNaaLocationFilter
from custom.intrahealth.sqldata import RecapPassageOneData
from dimagi.utils.dates import force_to_date


class RecapPassageOneReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    slug = 'recap_passage_1'
    comment = 'recap passage 1'
    name = 'Recap Passage 1'
    default_rows = 10
    exportable = True

    report_template_path = 'yeksi_naa/recap_passage.html'

    @property
    def export_table(self):
        report = [
        ]
        visits = self.calculate_table()
        for visit in visits.values():
            report_sheet = []
            report_sheet.append(
                "{}_{}".format(
                    visit['title'].replace(' ', '_'),
                    visit['comment'].strftime("%Y_%b_%d")
                )
            )
            report_sheet.append([
                [x.html for x in visit['headers'].header],
                *visit['rows']
            ])
            report.append(report_sheet)
        return report

    @property
    def fields(self):
        return [DateRangeFilter, RecapPassageOneProgramFilter, YeksiRecapPassageNaaLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @property
    def report_context(self):
        if not self.needs_filters:
            return {
                'report': self.get_report_context(),
                'title': self.name
            }
        return {}

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
        headers = RecapPassageOneData(config=self.config).headers.header
        return DataTablesHeader(
            *(headers[:2])
        )

    @property
    def comment(self):
        choosen_product = RecapPassageOneData(config=self.config).program_name
        return choosen_product or None

    def aggregated_rows(self):
        headers = RecapPassageOneData(config=self.config).headers.header
        return DataTablesHeader(
            DataTablesColumn('uno'),
            DataTablesColumn('dos'),
        )

    def get_report_context(self):
        if self.needs_filters:
            visits = []
            aggregated_headers = []
            aggregated_rows = []
            comment = ""

        else:
            visits = self.calculate_table()

            aggregated_rows, aggregated_headers = self.calculate_aggregated_table()
            
            for n in range(len(aggregated_headers)):
                aggregated_headers.header[n].row = aggregated_rows[n]

            comment = self.comment

        context = {
            'report_table': {
                'title': self.name,
                'slug': self.slug,
                'comment': comment,
                'project': self.request.GET.get('project_name') or "Malaria",
                'default_rows': self.default_rows,
                'visits': sorted(visits.values(), key=lambda visit: visit['comment'], reverse=True)
            },
            'aggregated_table': {
                'headers': aggregated_headers,
                'rows': aggregated_rows,
                'number_of_agregated': 2
            }
        }

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
        config = {
            'domain': self.domain,
        }
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
