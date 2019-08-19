# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

import datetime

from django.utils.functional import cached_property

from corehq.apps.hqwebapp.decorators import use_nvd3
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import YeksiNaaLocationFilter, ProgramsAndProductsFilter, DateRangeFilter
from custom.intrahealth.sqldata import VisiteDeLOperateurPerProductV2DataSource
from dimagi.utils.dates import force_to_date


class DisponibiliteReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    name = "Disponibilité"
    slug = 'disponibilite_report'
    comment = 'Taux de disponibilité de la gamme'
    default_rows = 10

    report_template_path = 'yeksi_naa/tabular_report.html'

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(DisponibiliteReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def fields(self):
        return [DateRangeFilter, ProgramsAndProductsFilter, YeksiNaaLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @property
    def report_context(self):
        context = {
            'report': self.get_report_context(),
            'charts': self.charts,
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
        return DataTablesHeader(
            DataTablesColumn(self.selected_location_type),
            DataTablesColumn('Taux de disponibilité de la Gamme des produits'),
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

    @property
    def clean_rows(self):
        return VisiteDeLOperateurPerProductV2DataSource(config=self.config).rows

    def calculate_rows(self):

        def to_report_row(s):
            stocks_to_return = []
            added_locations = []
            added_locations_with_products = {}

            for stock in s:
                location_id = stock['location_id']
                location_name = stock['location_name']
                products = stock['products']
                if location_id in added_locations:
                    in_ppses = added_locations_with_products[location_name][0]
                    all_ppses = added_locations_with_products[location_name][1]
                    for product in products:
                        in_ppses += product['in_ppses']
                        all_ppses += product['all_ppses']
                    added_locations_with_products[location_name][0] = in_ppses
                    added_locations_with_products[location_name][1] = all_ppses
                else:
                    added_locations.append(location_id)
                    in_ppses = 0
                    all_ppses = 0
                    for product in products:
                        in_ppses += product['in_ppses']
                        all_ppses += product['all_ppses']
                    added_locations_with_products[location_name] = [in_ppses, all_ppses]

            for location, products in added_locations_with_products.items():
                in_ppses = products[0]
                all_ppses = products[1]
                percent = (in_ppses / float(all_ppses)) * 100
                stocks_to_return.append([
                    location,
                    {
                        'html': '{:.2f} %'.format(percent),
                        'sort_key': percent,
                    }
                ])

            return stocks_to_return

        def calculate_total_row(s):
            total_row_to_return = ['<b>NATIONAL</b>']
            all_ppses = 0
            in_ppses = 0

            for stock in s:
                products = stock['products']
                for product in products:
                    all_ppses += product['all_ppses']
                    in_ppses += product['in_ppses']

            percent = (in_ppses / float(all_ppses)) * 100 if all_ppses is not 0 else 0
            total_row_to_return.append({
                'html': '<b>{:.2f} %</b>'.format(percent),
                'sort_key': percent,
            })

            return total_row_to_return

        rows = to_report_row(self.clean_rows)
        total_row = calculate_total_row(self.clean_rows)
        rows.append(total_row)
        return rows

    @property
    def charts(self):
        chart = MultiBarChart(None, Axis('Location'), Axis('Percent', format='.2f'))
        chart.height = 400
        chart.marginBottom = 100

        def get_data_for_graph():
            com = []
            rows = self.calculate_rows()
            rows.pop()
            for row in rows:
                com.append({"x": row[0], "y": row[1]['sort_key']})

            return [
                {"key": "Taux de disponibilité de la Gamme des produits ", 'values': com},
            ]

        chart.data = get_data_for_graph()
        return [chart]

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
        config['product_product'] = self.request.GET.get('product_product')
        config['selected_location'] = self.request.GET.get('location_id')
        return config
