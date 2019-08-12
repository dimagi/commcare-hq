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
        quantities = SatisfactionRateAfterDeliveryPerProductData(config=self.config).rows
        loc_type = self.selected_location_type.lower()
        quantities_list = []

        for quantity in quantities:
            data_dict = {
                'location_name': quantity['{}_name'.format(loc_type)],
                'location_id': quantity['{}_id'.format(loc_type)],
                'products': [],
            }
            product_name = quantity['product_name']
            product_id = quantity['product_id']
            amt_delivered_convenience = quantity['amt_delivered_convenience']
            ideal_topup = quantity['ideal_topup']

            length = len(quantities_list)
            if not quantities_list:
                product_dict = {
                    'product_name': product_name,
                    'product_id': product_id,
                    'amt_delivered_convenience': amt_delivered_convenience,
                    'ideal_topup': ideal_topup,
                }
                data_dict['products'].append(product_dict)
                quantities_list.append(data_dict)
            else:
                for r in range(0, length):
                    location_id = quantities_list[r]['location_id']
                    if quantity['{}_id'.format(loc_type)] == location_id:
                        if not quantities_list[r]['products']:
                            product_dict = {
                                'product_name': product_name,
                                'product_id': product_id,
                                'amt_delivered_convenience': amt_delivered_convenience,
                                'ideal_topup': ideal_topup,
                            }
                            quantities_list[r]['products'].append(product_dict)
                        else:
                            products = quantities_list[r]['products']
                            amount_of_products = len(products)
                            for s in range(0, amount_of_products):
                                product = products[s]
                                if product['product_id'] == product_id:
                                    product['amt_delivered_convenience'] += amt_delivered_convenience
                                    product['ideal_topup'] += ideal_topup
                                    break
                                elif product['product_id'] != product_id and s == amount_of_products - 1:
                                    product_dict = {
                                        'product_name': product_name,
                                        'product_id': product_id,
                                        'amt_delivered_convenience': amt_delivered_convenience,
                                        'ideal_topup': ideal_topup,
                                    }
                                    quantities_list[r]['products'].append(product_dict)
                    elif quantity['{}_id'.format(loc_type)] != location_id and r == length - 1:
                        product_dict = {
                            'product_name': product_name,
                            'product_id': product_id,
                            'amt_delivered_convenience': amt_delivered_convenience,
                            'ideal_topup': ideal_topup,
                        }
                        data_dict['products'].append(product_dict)
                        quantities_list.append(data_dict)

        return quantities_list

    def calculate_rows(self):

        def data_to_rows(quantities_list):
            quantities_to_return = []
            product_names = []
            product_ids = []
            for quantity in quantities_list:
                for product in quantity['products']:
                    product_name = product['product_name']
                    product_id = product['product_id']
                    if product_id not in product_ids:
                        product_ids.append(product_id)
                        product_names.append(product_name)

            for quantity in quantities_list:
                products_list = []
                location_name = quantity['location_name']
                for product in quantity['products']:
                    products_list.append(product)
                products_names_from_list = [x['product_name'] for x in quantity['products']]
                for product_name in product_names:
                    if product_name not in products_names_from_list:
                        products_list.append({
                            'product_name': product_name,
                            'amt_delivered_convenience': 0,
                            'ideal_topup': 0,
                        })
                quantities_to_return.append([
                    location_name,
                ])
                products_list = sorted(products_list, key=lambda x: x['product_name'])
                for product_info in products_list:
                    amt_delivered_convenience = product_info['amt_delivered_convenience']
                    ideal_topup = product_info['ideal_topup']
                    percent_formatted = 'pas de données'
                    percent = (amt_delivered_convenience / float(ideal_topup)) * 100 \
                        if ideal_topup > 0 else percent_formatted
                    if percent is not 'pas de données':
                        percent_formatted = '{:.2f} %'.format(percent)
                    quantities_to_return[-1].append({
                        'html': '{}'.format(percent_formatted),
                        'sort_key': percent_formatted
                    })

            return quantities_to_return

        rows = data_to_rows(self.clean_rows)

        return rows

    @property
    def charts(self):
        chart = PieChart('Taux de Satisfaction des produits au niveau national',
                         'produits proposes sur produits livres', [])

        def data_to_chart(quantities_list):
            products_names_list = []
            products_occurences = {}
            products_data = {}
            product_names = []

            for quantity in quantities_list:
                products_list = []
                for product in quantity['products']:
                    products_list.append(product)
                    if product['product_name'] not in product_names:
                        product_names.append(product['product_name'])
                products_names_from_list = [x['product_name'] for x in quantity['products']]
                for product_name in product_names:
                    if product_name not in products_names_from_list:
                        products_list.append({
                            'product_name': product_name,
                            'amt_delivered_convenience': 0,
                            'ideal_topup': 0,
                        })

                for product in products_list:
                    product_name = product['product_name']
                    amt_delivered_convenience = product['amt_delivered_convenience']
                    ideal_topup = product['ideal_topup']
                    if product_name not in products_names_list:
                        products_names_list.append(product_name)
                        products_occurences[product_name] = 1
                        products_data[product_name] = [amt_delivered_convenience, ideal_topup]
                    else:
                        products_occurences[product_name] += 1
                        products_data[product_name][0] += amt_delivered_convenience
                        products_data[product_name][1] += ideal_topup

            chart_pertencts = []
            for product in product_names:
                amt_delivered_convenience = products_data[product][0]
                ideal_topup = products_data[product][1]
                product_occurences = products_occurences[product]
                percent = ((amt_delivered_convenience / float(ideal_topup)) * 100) / product_occurences
                chart_pertencts.append([product, percent])

            return chart_pertencts

        def get_data_for_graph():
            chart_percents = data_to_chart(self.clean_rows)

            return [
                {'label': x[0], 'value': x[1]} for x in chart_percents
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
