# coding=utf-8

import datetime

from django.utils.functional import cached_property

from corehq.apps.hqwebapp.decorators import use_nvd3
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import Axis
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import YeksiNaaLocationFilter, ProgramsAndProductsFilter, DateRangeFilter
from custom.intrahealth.sqldata import VisiteDeLOperateurPerProductV2DataSource
from dimagi.utils.dates import force_to_date

from custom.intrahealth.utils import PNAMultiBarChart


class DisponibiliteReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    name = "Disponibilité"
    slug = 'disponibilite_report'
    comment = 'Taux de disponibilité de la gamme'
    default_rows = 10
    exportable = True

    report_template_path = 'yeksi_naa/tabular_report.html'

    @property
    def export_table(self):
        report = [
            [
                'Disponibilité',
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
            'charts': self.charts if not self.needs_filters else None,
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

        if self.selected_location_type != 'PPS':
            products = self.products
            for product in products:
                headers.add_column(DataTablesColumn(product))
        else:
            headers.add_column(DataTablesColumn('Produits disponibles'))

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
        return VisiteDeLOperateurPerProductV2DataSource(config=self.config).rows

    def calculate_rows(self):

        def data_to_rows(stocks_list):
            stocks_to_return = []
            added_locations = []
            locations_with_products = {}
            all_products = self.products

            for stock in stocks_list:
                location_id = stock['location_id']
                location_name = stock['location_name']
                products = sorted(stock['products'], key=lambda x: x['product_name'])
                if location_id in added_locations:
                    length = len(locations_with_products[location_name])
                    for r in range(0, length):
                        product_for_location = locations_with_products[location_name][r]
                        for product in products:
                            if product_for_location['product_id'] == product['product_id']:
                                in_ppses = product['in_ppses']
                                all_ppses = product['all_ppses']
                                locations_with_products[location_name][r]['in_ppses'] += in_ppses
                                locations_with_products[location_name][r]['all_ppses'] += all_ppses
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
                            in_ppses = product['in_ppses']
                            all_ppses = product['all_ppses']
                            products_to_add[index]['in_ppses'] += in_ppses
                            products_to_add[index]['all_ppses'] += all_ppses

                    for product in products_to_add:
                        locations_with_products[location_name].append(product)

            for location, products in locations_with_products.items():
                products_names = [x['product_name'] for x in products]
                for product_name in all_products:
                    if product_name not in products_names:
                        locations_with_products[location].append({
                            'product_id': None,
                            'product_name': product_name,
                            'in_ppses': 0,
                            'all_ppses': 0,
                        })

            if self.selected_location_type != 'PPS':
                for location, products in locations_with_products.items():
                    stocks_to_return.append([
                        location,
                    ])
                    products_list = sorted(products, key=lambda x: x['product_name'])
                    for product_info in products_list:
                        in_ppses = product_info['in_ppses']
                        all_ppses = product_info['all_ppses']
                        percent = (in_ppses / float(all_ppses) * 100) \
                            if all_ppses != 0 else 'pas de données'
                        if percent != 'pas de données':
                            percent = '{:.2f} %'.format(percent)
                        stocks_to_return[-1].append({
                            'html': '{}'.format(percent),
                            'sort_key': percent,
                        })
            else:
                for location, products in locations_with_products.items():
                    stocks_to_return.append([
                        location,
                    ])
                    products_list = sorted(products, key=lambda x: x['product_name'])
                    in_ppses = 0
                    all_ppses = 0
                    for product_info in products_list:
                        in_ppses += product_info['in_ppses']
                        all_ppses += product_info['all_ppses']
                    percent = (in_ppses / float(all_ppses) * 100) \
                        if all_ppses != 0 else 'pas de données'
                    if percent != 'pas de données':
                        percent = '{:.2f} %'.format(percent)
                    stocks_to_return[-1].append({
                        'html': '{}'.format(percent),
                        'sort_key': percent,
                    })

            total_row = calculate_total_row(locations_with_products)
            stocks_to_return.append(total_row)

            return stocks_to_return

        def calculate_total_row(locations_with_products):
            total_row_to_return = ['<b>SYNTHESE</b>']
            data_for_total_row = []

            for location, products in locations_with_products.items():
                products_list = sorted(products, key=lambda x: x['product_name'])
                if not data_for_total_row:
                    for product_info in products_list:
                        in_ppses = product_info['in_ppses']
                        all_ppses = product_info['all_ppses']
                        data_for_total_row.append([in_ppses, all_ppses])
                else:
                    for r in range(0, len(products_list)):
                        product_info = products_list[r]
                        in_ppses = product_info['in_ppses']
                        all_ppses = product_info['all_ppses']
                        data_for_total_row[r][0] += in_ppses
                        data_for_total_row[r][1] += all_ppses

            if self.selected_location_type != 'PPS':
                for data in data_for_total_row:
                    in_ppses = data[0]
                    all_ppses = data[1]
                    percent = (in_ppses / float(all_ppses) * 100) \
                        if all_ppses != 0 else 0
                    total_row_to_return.append({
                        'html': '<b>{:.2f} %</b>'.format(percent),
                        'sort_key': percent,
                    })
            else:
                in_ppses = sum(x[0] for x in data_for_total_row)
                all_ppses = sum(x[1] for x in data_for_total_row)
                percent = (in_ppses / float(all_ppses) * 100) \
                    if all_ppses != 0 else 0
                total_row_to_return.append({
                    'html': '<b>{:.2f} %</b>'.format(percent),
                    'sort_key': percent,
                })

            return total_row_to_return

        rows = data_to_rows(self.clean_rows)

        return rows

    @property
    def charts(self):
        chart = PNAMultiBarChart(None, Axis('Product'), Axis('Percent', format='.2f'))
        chart.height = 550
        chart.marginBottom = 150
        chart.forceY = [0, 100]
        chart.rotateLabels = -45
        chart.showControls = False

        def data_to_chart(stocks_list):
            stocks_to_return = []
            products_data = []
            added_products = []

            for stock in stocks_list:
                location_id = stock['location_id']
                location_name = stock['location_name']
                for product in stock['products']:
                    product_id = product['product_id']
                    product_name = product['product_name']
                    in_ppses = product['in_ppses']
                    all_ppses = product['all_ppses']
                    if product_id not in added_products:
                        added_products.append(product_id)
                        product_dict = {
                            'product_id': product_id,
                            'product_name': product_name,
                            'location_id': location_id,
                            'location_name': location_name,
                            'in_ppses': in_ppses,
                            'all_ppses': all_ppses,
                        }
                        products_data.append(product_dict)
                    else:
                        for product_data in products_data:
                            if product_data['product_id'] == product_id:
                                product_data['in_ppses'] += in_ppses
                                product_data['all_ppses'] += all_ppses

            products = sorted(products_data, key=lambda x: x['product_name'])
            if self.selected_location_type != 'PPS':
                for product in products:
                    product_name = product['product_name']
                    in_ppses = product['in_ppses']
                    all_ppses = product['all_ppses']
                    percent = (in_ppses / float(all_ppses)) * 100 if all_ppses != 0 else 0
                    stocks_to_return.append([
                        product_name,
                        {
                            'html': '{}'.format(percent),
                            'sort_key': percent
                        }
                    ])
            else:
                added_locations = []
                availability_for_ppses = {}
                for product in products:
                    location_id = product['location_id']
                    location_name = product['location_name']
                    in_ppses = product['in_ppses']
                    all_ppses = product['all_ppses']
                    if location_id not in added_locations:
                        added_locations.append(location_id)
                        availability_for_ppses[location_id] = {
                            'location_name': location_name,
                            'in_ppses': in_ppses,
                            'all_ppses': all_ppses,
                        }
                    else:
                        availability_for_ppses[location_id]['in_ppses'] += in_ppses
                        availability_for_ppses[location_id]['all_ppses'] += all_ppses

                for location_id, location_info in availability_for_ppses.items():
                    location_name = location_info['location_name']
                    in_ppses = location_info['in_ppses']
                    all_ppses = location_info['all_ppses']
                    percent = (in_ppses / float(all_ppses)) * 100 if all_ppses != 0 else 0
                    stocks_to_return.append([
                        location_name,
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
                    "key": 'Taux de disponibilité de la Gamme des produits',
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
