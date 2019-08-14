# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

from django.utils.functional import cached_property

from corehq.apps.hqwebapp.decorators import use_nvd3
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import YeksiNaaLocationFilter, ProgramsAndProductsFilter
from custom.intrahealth.sqldata import ConsommationPerProductData


class ConsommationReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    name = "Consommation"
    slug = 'consommation_report'
    comment = 'Consommation de la gamme par produit'
    default_rows = 10

    report_template_path = 'yeksi_naa/tabular_report.html'

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(ConsommationReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def fields(self):
        return [ProgramsAndProductsFilter, YeksiNaaLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @property
    def report_context(self):
        context = {
            'report': self.get_report_context(),
            'title': self.name,
            'charts': self.charts
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

        return headers

    @property
    def clean_rows(self):
        return ConsommationPerProductData(config=self.config).rows

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

        def data_to_rows(consumptions_list):
            consumptions_to_return = []
            added_locations = []
            locations_with_products = {}
            all_products = self.products

            for consumption in consumptions_list:
                location_id = consumption['location_id']
                location_name = consumption['location_name']
                products = sorted(consumption['products'], key=lambda x: x['product_name'])
                if location_id in added_locations:
                    length = len(locations_with_products[location_name])
                    for r in range(0, length):
                        product_for_location = locations_with_products[location_name][r]
                        for product in products:
                            if product_for_location['product_id'] == product['product_id']:
                                actual_consumption = product['actual_consumption']
                                locations_with_products[location_name][r]['actual_consumption'] += actual_consumption
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
                            actual_consumption = product['actual_consumption']
                            products_to_add[index]['actual_consumption'] += actual_consumption

                    for product in products_to_add:
                        locations_with_products[location_name].append(product)

            for location, products in locations_with_products.items():
                products_names = [x['product_name'] for x in products]
                for product_name in all_products:
                    if product_name not in products_names:
                        locations_with_products[location].append({
                            'product_id': None,
                            'product_name': product_name,
                            'actual_consumption': 0,
                        })

            for location, products in locations_with_products.items():
                consumptions_to_return.append([
                    location,
                ])
                products_list = sorted(products, key=lambda x: x['product_name'])
                for product_info in products_list:
                    actual_consumption = product_info['actual_consumption']
                    product_id = product_info['product_id']
                    consumption = actual_consumption if product_id is not None else 'pas de données'
                    consumptions_to_return[-1].append({
                        'html': '{}'.format(consumption),
                        'sort_key': consumption
                    })

            return consumptions_to_return

        rows = data_to_rows(self.clean_rows)

        return rows

    @property
    def charts(self):
        chart = MultiBarChart(None, Axis('Location'), Axis('Amount', format='i'))
        chart.height = 400
        chart.marginBottom = 100

        def data_to_chart(stocks_list):
            stocks_to_return = []
            products_data = []
            added_products = []

            for stock in stocks_list:
                sorted_stock = sorted(stock['products'], key=lambda x: x['product_name'])
                for product in sorted_stock:
                    product_id = product['product_id']
                    product_name = product['product_name']
                    actual_consumption = product['actual_consumption']
                    if product_id not in added_products:
                        added_products.append(product_id)
                        product_dict = {
                            'product_id': product_id,
                            'product_name': product_name,
                            'actual_consumption': actual_consumption,
                        }
                        products_data.append(product_dict)
                    else:
                        for product_data in products_data:
                            if product_data['product_id'] == product_id:
                                product_data['actual_consumption'] += actual_consumption

            products = sorted(products_data, key=lambda x: x['product_name'])
            for product in products:
                product_name = product['product_name']
                actual_consumption = product['actual_consumption']
                consumption = actual_consumption if actual_consumption is not 0 else 0
                stocks_to_return.append([
                    product_name,
                    {
                        'html': '{}'.format(consumption),
                        'sort_key': consumption
                    }
                ])

            return stocks_to_return

        def get_data_for_graph():
            com = []
            rows = data_to_chart(self.clean_rows)
            for row in rows:
                com.append({"x": row[0], "y": row[1]['sort_key']})

            return [
                {
                    "key": 'Taux de rupture par produit au niveau national',
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
        config['product_program'] = self.request.GET.get('product_program')
        config['product_product'] = self.request.GET.get('product_product')
        config['selected_location'] = self.request.GET.get('location_id')
        return config
