# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

import datetime

from django.utils.functional import cached_property

from corehq.apps.hqwebapp.decorators import use_nvd3
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import Axis
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import DateRangeFilter, ProgramsAndProductsFilter, YeksiNaaLocationFilter
from custom.intrahealth.sqldata import ValuationOfPNAStockPerProductV2Data
from dimagi.utils.dates import force_to_date

from custom.intrahealth.utils import PNAMultiBarChart


class ValuerDesStocksPNADisponsibleReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    slug = 'valeur_des_stocks_pna_disponible_report'
    comment = 'Valeur des stocks PNA disponible'
    name = 'Valeur des stocks PNA disponible'
    default_rows = 10
    exportable = True

    report_template_path = 'yeksi_naa/tabular_report.html'

    @property
    def export_table(self):
        report = [
            [
                'Valuer des stocks PNA disponible',
                [],
            ]
        ]
        headers = [x.html for x in self.headers]
        rows = self.calculate_rows()
        report[0][1].append(headers)

        for row in rows:
            location_name = row[0]
            location_name = location_name.replace('<b>', '')
            location_name = location_name.replace('</b>', '')

            row_to_return = [location_name]

            rows_length = len(row)
            for r in range(1, rows_length):
                value = row[r]['html']
                value = value.replace('<b>', '')
                value = value.replace('</b>', '')
                row_to_return.append(value)

            report[0][1].append(row_to_return)

        return report

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(ValuerDesStocksPNADisponsibleReport, self).decorator_dispatcher(request, *args, **kwargs)

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
            'title': self.name,
            'charts': self.charts if not self.needs_filters else None
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
    def products(self):
        products_names = []

        for row in self.clean_rows:
            for product_info in row['products']:
                product_name = product_info['product_name']
                if product_name not in products_names:
                    products_names.append(product_name)

        products_names = sorted(products_names)

        return products_names

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(self.selected_location_type),
        )

        products = self.products
        for product in products:
            headers.add_column(DataTablesColumn(product))

        headers.add_column(DataTablesColumn('SYNTHESE'))

        return headers

    @property
    def clean_rows(self):
        return ValuationOfPNAStockPerProductV2Data(config=self.config).rows

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

        def data_to_rows(pnas_list):
            pnas_to_return = []
            added_locations = []
            locations_with_products = {}
            all_products = self.products

            for pna in pnas_list:
                location_id = pna['location_id']
                location_name = pna['location_name']
                products = sorted(pna['products'], key=lambda x: x['product_name'])
                if location_id in added_locations:
                    length = len(locations_with_products[location_name])
                    for r in range(0, length):
                        product_for_location = locations_with_products[location_name][r]
                        for product in products:
                            if product_for_location['product_id'] == product['product_id']:
                                final_pna_stock_valuation = product['final_pna_stock_valuation']
                                locations_with_products[location_name][r]['final_pna_stock_valuation'] += \
                                    final_pna_stock_valuation
                else:
                    added_locations.append(location_id)
                    locations_with_products[location_name] = []
                    unique_products_for_location = []
                    products_to_add = []
                    for product in products:
                        product_name = product['product_name']
                        if product_name not in unique_products_for_location and product_name in all_products:
                            unique_products_for_location.append(product_name)
                            products_to_add.append(product)
                        else:
                            index = unique_products_for_location.index(product_name)
                            final_pna_stock_valuation = product['final_pna_stock_valuation']
                            products_to_add[index]['final_pna_stock_valuation'] += final_pna_stock_valuation

                    for product in products_to_add:
                        locations_with_products[location_name].append(product)

            for location, products in locations_with_products.items():
                products_names = [x['product_name'] for x in products]
                for product_name in all_products:
                    if product_name not in products_names:
                        locations_with_products[location].append({
                            'product_id': None,
                            'product_name': product_name,
                            'final_pna_stock_valuation': 0,
                        })

            for location, products in locations_with_products.items():
                pnas_to_return.append([
                    location,
                ])
                products_list = sorted(products, key=lambda x: x['product_name'])
                for product_info in products_list:
                    actual_consumption = product_info['final_pna_stock_valuation']
                    product_id = product_info['product_id']
                    pna = actual_consumption if product_id is not None else 'pas de données'
                    pnas_to_return[-1].append({
                        'html': '{}'.format(pna),
                        'sort_key': pna
                    })

            total_row = calculate_total_row(locations_with_products)
            pnas_to_return.append(total_row)
            pnas_to_return = add_total_column(locations_with_products, pnas_to_return)

            return pnas_to_return

        def add_total_column(locations_with_products, pnas_to_return):
            length = len(pnas_to_return)
            for location, products in locations_with_products.items():
                locations_final_pna_stock_valuation = 0
                for product in products:
                    locations_final_pna_stock_valuation += product['final_pna_stock_valuation']
                for r in range(0, length):
                    current_location = pnas_to_return[r][0]
                    if current_location == location:
                        pnas_to_return[r].append({
                                'html': '<b>{}</b>'.format(locations_final_pna_stock_valuation),
                                'sort_key': locations_final_pna_stock_valuation
                            })

            return pnas_to_return

        def calculate_total_row(locations_with_products):
            total_row_to_return = ['<b>SYNTHESE</b>']
            locations_with_products['<b>SYNTHESE</b>'] = []
            data_for_total_row = []

            for location, products in locations_with_products.items():
                products_list = sorted(products, key=lambda x: x['product_name'])
                if not data_for_total_row:
                    for product_info in products_list:
                        final_pna_stock_valuation = product_info['final_pna_stock_valuation']
                        product_name = product_info['product_name']
                        data_for_total_row.append([final_pna_stock_valuation, product_name])
                else:
                    for r in range(0, len(products_list)):
                        product_info = products_list[r]
                        final_pna_stock_valuation = product_info['final_pna_stock_valuation']
                        data_for_total_row[r][0] += final_pna_stock_valuation

            for data in data_for_total_row:
                final_pna_stock_valuation = data[0]
                product_name = data[1]
                locations_with_products['<b>SYNTHESE</b>'].append({
                    'final_pna_stock_valuation': final_pna_stock_valuation,
                    'product_name': product_name,
                })
                total_row_to_return.append({
                    'html': '<b>{}</b>'.format(final_pna_stock_valuation),
                    'sort_key': final_pna_stock_valuation,
                })

            return total_row_to_return

        rows = data_to_rows(self.clean_rows)

        return rows

    @property
    def charts(self):
        chart = PNAMultiBarChart(None, Axis('Location'), Axis('Amount', format='i'))
        chart.height = 550
        chart.marginBottom = 150
        chart.rotateLabels = -45
        chart.showControls = False

        def data_to_chart(quantities_list):
            quantities_to_return = []
            locations_data = {}
            added_locations = []

            quantities_list = sorted(quantities_list, key=lambda x: x['location_name'])
            for quantity in quantities_list:
                location_name = quantity['location_name']
                location_id = quantity['location_id']
                for product in quantity['products']:
                    final_pna_stock_valuation = product['final_pna_stock_valuation']
                    if location_id not in added_locations:
                        added_locations.append(location_id)
                        locations_data[location_id] = {
                            'location_name': location_name,
                            'final_pna_stock_valuation': final_pna_stock_valuation,
                        }
                    else:
                        locations_data[location_id]['final_pna_stock_valuation'] += final_pna_stock_valuation

            sorted_locations_data_values = sorted(locations_data.values(), key=lambda x: x['location_name'])
            for location_info in sorted_locations_data_values:
                location_name = location_info['location_name']
                final_pna_stock_valuation = location_info['final_pna_stock_valuation']
                pna = final_pna_stock_valuation if final_pna_stock_valuation is not 0 else 0
                quantities_to_return.append([
                    location_name,
                    {
                        'html': '{:.2f} %'.format(pna),
                        'sort_key': pna
                    }
                ])

            return quantities_to_return

        def get_data_for_graph():
            com = []
            rows = data_to_chart(self.clean_rows)
            for row in rows:
                com.append({"x": row[0], "y": row[1]['sort_key']})

            return [
                {
                    "key": 'Valeur des stocks PNA disponible',
                    'values': com
                },
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
