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
    comment = 'Consommation de la gamme par produit et par Region'
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
    def headers(self):
        def get_products():
            products_names = []

            for row in self.clean_rows:
                for product_info in row['products']:
                    product_name = product_info['product_name']
                    if product_name not in products_names:
                        products_names.append(product_name)

            return products_names

        headers = DataTablesHeader(
            DataTablesColumn(self.selected_location_type),
        )

        products = get_products()
        for product in products:
            headers.add_column(DataTablesColumn(product))

        return headers

    @property
    def clean_rows(self):
        consumptions = ConsommationPerProductData(config=self.config).rows
        loc_type = self.selected_location_type.lower()
        consumptions_list = []

        for consumption in consumptions:
            data_dict = {
                'location_name': consumption['{}_name'.format(loc_type)],
                'location_id': consumption['{}_id'.format(loc_type)],
                'products': [],
            }
            product_name = consumption['product_name']
            product_id = consumption['product_id']
            actual_consumption = consumption['actual_consumption']

            length = len(consumptions_list)
            if not consumptions_list:
                product_dict = {
                    'product_name': product_name,
                    'product_id': product_id,
                    'actual_consumption': actual_consumption,
                }
                data_dict['products'].append(product_dict)
                consumptions_list.append(data_dict)
            else:
                for r in range(0, length):
                    location_id = consumptions_list[r]['location_id']
                    if consumption['{}_id'.format(loc_type)] == location_id:
                        if not consumptions_list[r]['products']:
                            product_dict = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'actual_consumption': actual_consumption,
                            }
                            consumptions_list[r]['products'].append(product_dict)
                        else:
                            products = consumptions_list[r]['products']
                            amount_of_products = len(products)
                            for s in range(0, amount_of_products):
                                product = products[s]
                                if product['product_id'] == product_id:
                                    product['actual_consumption'] += actual_consumption
                                    break
                                elif product['product_id'] != product_id and s == amount_of_products - 1:
                                    product_dict = {
                                        'product_name': product_name,
                                        'product_id': product_id,
                                        'actual_consumption': actual_consumption,
                                    }
                                    consumptions_list[r]['products'].append(product_dict)
                    elif consumption['{}_id'.format(loc_type)] != location_id and r == length - 1:
                        product_dict = {
                            'product_name': product_name,
                            'product_id': product_id,
                            'actual_consumption': actual_consumption,
                        }
                        data_dict['products'].append(product_dict)
                        consumptions_list.append(data_dict)

        return consumptions_list

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
            product_names = []
            product_ids = []
            for consumption in consumptions_list:
                for product in consumption['products']:
                    product_name = product['product_name']
                    product_id = product['product_id']
                    if product_id not in product_ids:
                        product_ids.append(product_id)
                        product_names.append(product_name)

            for consumption in consumptions_list:
                products_list = []
                location_name = consumption['location_name']
                for product in consumption['products']:
                    products_list.append(product)
                products_names_from_list = [x['product_name'] for x in consumption['products']]
                for product_name in product_names:
                    if product_name not in products_names_from_list:
                        products_list.append({
                            'product_name': product_name,
                            'actual_consumption': 0,
                        })
                consumptions_to_return.append([
                    location_name,
                ])
                products_list = sorted(products_list, key=lambda x: x['product_name'])
                for product_info in products_list:
                    consumption_data = product_info['actual_consumption']
                    product_consumption = consumption_data if consumption_data > 0 else 'pas de données'
                    consumptions_to_return[-1].append({
                        'html': '{}'.format(product_consumption),
                        'sort_key': product_consumption
                    })

            return consumptions_to_return

        rows = data_to_rows(self.clean_rows)
        return rows

    @property
    def charts(self):
        chart = MultiBarChart(None, Axis('Location'), Axis('Amount', format='i'))
        chart.height = 400
        chart.marginBottom = 100

        def data_to_chart(consumptions_list):
            consumptions_to_return = []
            products_names_list = []
            products_ids_list = []
            products_actual_consumption_list = []
            for consumption in consumptions_list:
                for product in consumption['products']:
                    product_name = product['product_name']
                    product_id = product['product_id']
                    actual_consumption = product['actual_consumption']
                    if product_id not in products_ids_list:
                        products_ids_list.append(product_id)
                        products_names_list.append(product_name)
                        products_actual_consumption_list.append(actual_consumption)
                    else:
                        position = products_ids_list.index(product_id)
                        products_actual_consumption_list[position] += actual_consumption

            products_info = list(zip(products_names_list, products_actual_consumption_list))
            for info in products_info:
                product_name = info[0]
                actual_consumption = info[1]
                consumptions_to_return.append([
                    product_name,
                    {
                        'html': '{}'.format(actual_consumption),
                        'sort_key': actual_consumption
                    }
                ])

            return consumptions_to_return

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
