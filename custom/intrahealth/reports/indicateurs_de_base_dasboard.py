# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

from django.utils.functional import cached_property

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport
from custom.intrahealth.filters import YeksiNaaLocationFilter, FRMonthFilter, FRYearFilter
from custom.intrahealth.reports.utils import YeksiNaaMonthYearMixin


class IndicateursDeBaseReport(CustomProjectReport, YeksiNaaMonthYearMixin):
    # TODO: we need new filters and Data
    slug = 'indicateurs_de_base'
    comment = 'indicateurs de base'
    name = 'Indicateurs de Base'
    default_rows = 10
    report_template_path = 'yeksi_naa/tabular_report.html'

    @property
    def fields(self):
        return [FRMonthFilter, FRYearFilter, YeksiNaaLocationFilter]

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
            DataTablesColumn('Date effective de livraison'),
            DataTablesColumn('Nombre de PPS enregistrés'),
            DataTablesColumn('Nombre de PPS visités'),
            DataTablesColumn('Taux de couverture'),
            DataTablesColumn('Taux de soumission')
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
        # TODO calculations
        rows = [
                   ['7 June 2019 - 31 August 2019', 500, 780, 25.2, 55.69],
                   ['1 June 2019 - 16 August 2019', 120, 600, 36.5, 45.45],
                   ['2 June 2019 - 11 August 2019', 444, 40, 66.7, 78.78],
                   ['2 July 2019 - 2 August 2019', 771, 200, 77.45, 89.58]
               ]
        return rows

    @property
    def config(self):
        config = dict(
            domain=self.domain,
        )
        # TODO not sure is it important see YeksiNaaMonthYearMixin property year and month
        config['month'] = self.request.GET.get('month')
        config['year'] = self.request.GET.get('year')
        # TODO add location district and region !!!
        return config
