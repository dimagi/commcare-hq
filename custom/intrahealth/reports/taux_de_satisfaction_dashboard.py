# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

import datetime

from django.utils.functional import cached_property

from corehq.apps.hqwebapp.decorators import use_nvd3
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import MultiBarChart, Axis, PieChart
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import DateRangeFilter, ProgramsAndProductsFilter, YeksiNaaLocationFilter
from custom.intrahealth.sqldata import SatisfactionRateAfterDeliveryPerProductData
from dimagi.utils.dates import force_to_date


class TauxDeSatisfactionReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    slug = 'taux_de_satisfaction_report'
    comment = 'produits proposés sur produits livrés'
    name = 'Taux de Satisfaction'
    default_rows = 10

    report_template_path = 'yeksi_naa/tabular_report.html'

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(TauxDeSatisfactionReport, self).decorator_dispatcher(request, *args, **kwargs)

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
        return SatisfactionRateAfterDeliveryPerProductData(config=self.config).rows

    def calculate_rows(self):
        for x in self.clean_rows:
            print(x)

        def data_to_rows(quantities_list):
            quantities_to_return = []
            added_locations = []
            locations_with_products = {}
            all_products = self.products

            for quantity in quantities_list:
                location_id = quantity['location_id']
                location_name = quantity['location_name']
                products = sorted(quantity['products'], key=lambda x: x['product_name'])
                if location_id in added_locations:
                    length = len(locations_with_products[location_name])
                    for r in range(0, length):
                        product_for_location = locations_with_products[location_name][r]
                        for product in products:
                            if product_for_location['product_id'] == product['product_id']:
                                amt_delivered_convenience = product['amt_delivered_convenience']
                                ideal_topup = product['ideal_topup']
                                locations_with_products[location_name][r]['amt_delivered_convenience'] += amt_delivered_convenience
                                locations_with_products[location_name][r]['ideal_topup'] += ideal_topup
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
                            amt_delivered_convenience = product['amt_delivered_convenience']
                            ideal_topup = product['ideal_topup']
                            products_to_add[index]['amt_delivered_convenience'] += amt_delivered_convenience
                            products_to_add[index]['ideal_topup'] += ideal_topup

                    for product in products_to_add:
                        locations_with_products[location_name].append(product)

            for location, products in locations_with_products.items():
                products_names = [x['product_name'] for x in products]
                for product_name in all_products:
                    if product_name not in products_names:
                        locations_with_products[location].append({
                            'product_id': None,
                            'product_name': product_name,
                            'amt_delivered_convenience': 0,
                            'ideal_topup': 0,
                        })

            for location, products in locations_with_products.items():
                quantities_to_return.append([
                    location,
                ])
                products_list = sorted(products, key=lambda x: x['product_name'])
                for product_info in products_list:
                    amt_delivered_convenience = product_info['amt_delivered_convenience']
                    ideal_topup = product_info['ideal_topup']
                    percent = (amt_delivered_convenience / float(ideal_topup) * 100) \
                        if ideal_topup != 0 else 'pas de données'
                    if percent != 'pas de données':
                        percent = '{:.2f} %'.format(percent)
                    quantities_to_return[-1].append({
                        'html': '{}'.format(percent),
                        'sort_key': percent
                    })

            total_row = calculate_total_row(locations_with_products)
            quantities_to_return.append(total_row)

            return quantities_to_return

        def calculate_total_row(locations_with_products):
            total_row_to_return = ['<b>NATIONAL</b>']
            data_for_total_row = []

            for location, products in locations_with_products.items():
                products_list = sorted(products, key=lambda x: x['product_name'])
                if not data_for_total_row:
                    for product_info in products_list:
                        amt_delivered_convenience = product_info['amt_delivered_convenience']
                        ideal_topup = product_info['ideal_topup']
                        data_for_total_row.append([amt_delivered_convenience, ideal_topup])
                else:
                    for r in range(0, len(products_list)):
                        product_info = products_list[r]
                        amt_delivered_convenience = product_info['amt_delivered_convenience']
                        ideal_topup = product_info['ideal_topup']
                        data_for_total_row[r][0] += amt_delivered_convenience
                        data_for_total_row[r][1] += ideal_topup

            for data in data_for_total_row:
                amt_delivered_convenience = data[0]
                ideal_topup = data[1]
                percent = (amt_delivered_convenience / float(ideal_topup) * 100) \
                    if ideal_topup != 0 else 0
                total_row_to_return.append({
                    'html': '<b>{:.2f} %</b>'.format(percent),
                    'sort_key': percent,
                })

            return total_row_to_return

        rows = data_to_rows(self.clean_rows)

        return rows

    @property
    def charts(self):
        chart = MultiBarChart(None, Axis('Location'), Axis('Percent', format='.2f'))
        chart.height = 400
        chart.marginBottom = 100

        for xd in self.clean_rows:
            print(xd)

        def data_to_chart(quantities_list):
            quantities_to_return = []
            products_data = []
            added_products = []

            for quantity in quantities_list:
                sorted_quantity = sorted(quantity['products'], key=lambda x: x['product_name'])
                for product in sorted_quantity:
                    product_id = product['product_id']
                    product_name = product['product_name']
                    amt_delivered_convenience = product['amt_delivered_convenience']
                    ideal_topup = product['ideal_topup']
                    if product_id not in added_products:
                        added_products.append(product_id)
                        product_dict = {
                            'product_id': product_id,
                            'product_name': product_name,
                            'amt_delivered_convenience': amt_delivered_convenience,
                            'ideal_topup': ideal_topup,
                        }
                        products_data.append(product_dict)
                    else:
                        for product_data in products_data:
                            if product_data['product_id'] == product_id:
                                product_data['amt_delivered_convenience'] += amt_delivered_convenience
                                product_data['ideal_topup'] += ideal_topup

            products = sorted(products_data, key=lambda x: x['product_name'])
            for product in products:
                product_name = product['product_name']
                amt_delivered_convenience = product['amt_delivered_convenience']
                ideal_topup = product['ideal_topup']
                percent = (amt_delivered_convenience / float(ideal_topup) * 100) \
                    if ideal_topup != 0 else 0
                quantities_to_return.append([
                    product_name,
                    {
                        'html': '{:.2f} %'.format(percent),
                        'sort_key': percent
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
                    "key": 'Taux de Satisfaction des produits au niveau national',
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
