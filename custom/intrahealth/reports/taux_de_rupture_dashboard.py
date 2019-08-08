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
from custom.intrahealth.sqldata import TauxDeRuptureRateData
from dimagi.utils.dates import force_to_date


class TauxDeRuptureReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    name = "Taux De Rupture"
    slug = 'taux_de_rupture_report'
    comment = 'Indicateur logistique: Taux de rupture par produit et par Region'
    default_rows = 10

    report_template_path = 'yeksi_naa/tabular_report.html'

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(TauxDeRuptureReport, self).decorator_dispatcher(request, *args, **kwargs)

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
        stocks = TauxDeRuptureRateData(config=self.config).rows
        stocks = sorted(stocks, key=lambda x: x['{}_name'.format(self.selected_location_type.lower())])

        stocks_list = []
        added_locations = []
        added_products_for_locations = {}

        for stock in stocks:
            location_name = stock['{}_name'.format(self.selected_location_type.lower())]
            location_id = stock['{}_id'.format(self.selected_location_type.lower())]
            product_name = stock['product_name']
            product_id = stock['product_id']
            data_dict = {
                'location_name': location_name,
                'location_id': location_id,
                'products': []
            }
            if location_id in added_locations:
                amount_of_stocks = len(stocks_list)

                location_position = 0
                for r in range(0, amount_of_stocks):
                    current_location = stocks_list[r]['location_id']
                    if current_location == location_id:
                        location_position = r
                        break

                added_products_for_location = [x['product_id'] for x in added_products_for_locations[location_id]]
                products_for_location = added_products_for_locations[location_id]
                if product_id not in added_products_for_location:
                    product_data = {
                        'product_name': product_name,
                        'product_id': product_id,
                        'out_in_ppses': 0,
                        'all_ppses': 0,
                    }
                    added_products_for_locations[location_id].append(product_data)
                    stocks_list[location_position]['products'].append(product_data)
                amount_of_products_for_location = len(added_products_for_locations[location_id])

                product_position = 0
                for s in range(0, amount_of_products_for_location):
                    current_product = products_for_location[s]['product_id']
                    if current_product == product_id:
                        product_position = s
                        break

                product_is_outstock = True if stock['product_is_outstock'] == 0 else False
                overall_position = stocks_list[location_position]['products'][product_position]
                if product_is_outstock:
                    overall_position['out_in_ppses'] += 1
                overall_position['all_ppses'] += 1
            else:
                added_locations.append(location_id)
                product_data = {
                    'product_name': product_name,
                    'product_id': product_id,
                    'out_in_ppses': 0,
                    'all_ppses': 0,
                }
                product_is_outstock = True if stock['product_is_outstock'] == 0 else False
                if product_is_outstock:
                    product_data['out_in_ppses'] += 1
                product_data['all_ppses'] += 1
                data_dict['products'].append(product_data)
                stocks_list.append(data_dict) 
                added_products_for_locations[location_id] = [product_data]

        stocks_list = sorted(stocks_list, key=lambda x: x['location_id'])

        return stocks_list

    def calculate_rows(self):

        def data_to_rows(stocks_list):
            stocks_to_return = []
            product_ids = []
            product_names = []
            for stock in stocks_list:
                for product in stock['products']:
                    product_name = product['product_name']
                    product_id = product['product_id']
                    if product_id not in product_ids:
                        product_ids.append(product_id)
                        product_names.append(product_name)

            for stock in stocks_list:
                products_list = []
                location_name = stock['location_name']
                for product in stock['products']:
                    products_list.append(product)
                products_names_from_list = [x['product_name'] for x in stock['products']]
                for product_name in product_names:
                    if product_name not in products_names_from_list:
                        products_list.append({
                            'product_name': product_name,
                            'out_in_ppses': 0,
                            'all_ppses': 0
                        })
                stocks_to_return.append([
                    location_name,
                ])

                products_list = sorted(products_list, key=lambda x: x['product_name'])
                for product_info in products_list:
                    product_available_in_ppses = product_info['out_in_ppses']
                    number_of_ppses = product_info['all_ppses']
                    percent = (product_available_in_ppses / float(number_of_ppses) * 100) if number_of_ppses != 0 else 0
                    stocks_to_return[-1].append({
                        'html': '{:.2f} %'.format(percent),
                        'sort_key': percent
                    })

            return stocks_to_return

        rows = data_to_rows(self.clean_rows)
        return rows

    @property
    def charts(self):
        chart = MultiBarChart(None, Axis('Product'), Axis('Percent', format='.2f'))
        chart.height = 400
        chart.marginBottom = 100

        def data_to_chart(stocks_list):
            stocks_to_return = []
            products_names_list = []
            products_ids_list = []
            products_dict = {}
            for stock in stocks_list:
                for product in stock['products']:
                    product_name = product['product_name']
                    product_id = product['product_id']
                    out_in_ppses = product['out_in_ppses']
                    all_ppses = product['all_ppses']
                    if product_id not in products_ids_list:
                        products_ids_list.append(product_id)
                        products_names_list.append(product_name)
                        products_dict[product_name] = [out_in_ppses, all_ppses]
                    else:
                        products_dict[product_name][0] += out_in_ppses
                        products_dict[product_name][1] += all_ppses
            for product, data in products_dict.items():
                out_in_ppses = data[0]
                all_ppses = data[1]
                percent = ((out_in_ppses) / float(all_ppses)) * 100 if all_ppses is not 0 else 0
                stocks_to_return.append([
                    product,
                    {
                        'html': '{}'.format(percent),
                        'sort_key': percent          
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
