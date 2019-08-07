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
    comment = 'test comment change me later'
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
            # 'charts': self.charts
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
            DataTablesColumn(self.selected_location_type),
            DataTablesColumn(
                'Consommation de la gamme par produit et par Region'
            ),
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
        consumptions = ConsommationPerProductData(config=self.config).rows

        def to_report_row(c):
            loc_type = self.selected_location_type.lower()
            consumptions_list = []
            consumptions_to_return = []

            for consumption in c:
                data_dict = {
                    'location_name': consumption['{}_name'.format(loc_type)],
                    'products': [],
                }
                product_name = consumption['product_name']
                actual_consumption = consumption['actual_consumption']

                length = len(consumptions_list)
                if not consumptions_list:
                    product_dict = {
                        'product_name': product_name,
                        'actual_consumption': actual_consumption,
                    }
                    data_dict['products'].append(product_dict)
                    consumptions_list.append(data_dict)
                else:
                    for r in range(0, length):
                        location_name = consumptions_list[r]['location_name']
                        if consumption['{}_name'.format(loc_type)] == location_name:
                            if not consumptions_list[r]['products']:
                                product_dict = {
                                    'product_name': product_name,
                                    'actual_consumption': actual_consumption,
                                }
                                consumptions_list[r]['products'].append(product_dict)
                            else:
                                products = consumptions_list[r]['products']
                                amount_of_products = len(products)
                                for s in range(0, amount_of_products):
                                    product = products[s]
                                    if product['product_name'] == product_name:
                                        product['actual_consumption'] += actual_consumption
                                        break
                                    elif product['product_name'] != product_name and s == amount_of_products - 1:
                                        product_dict = {
                                            'product_name': product_name,
                                            'actual_consumption': actual_consumption,
                                        }
                                        consumptions_list[r]['products'].append(product_dict)
                        elif consumption['{}_name'.format(loc_type)] != location_name and r == length - 1:
                            product_dict = {
                                'product_name': product_name,
                                'actual_consumption': actual_consumption,
                            }
                            data_dict['products'].append(product_dict)
                            consumptions_list.append(data_dict)

            for consumption in consumptions_list:
                for product in consumption['products']:
                    location_name = consumption['location_name']
                    product_name = product['product_name']
                    actual_consumption = product['actual_consumption']
                    consumptions_to_return.append([
                        location_name,
                        product_name,
                        {
                            'html': '{}'.format(actual_consumption),
                            'sort_key': actual_consumption
                        }
                    ])

            return consumptions_to_return

        rows = to_report_row(consumptions)
        return rows

    @property
    def charts(self):
        chart = MultiBarChart(None, Axis('Location'), Axis('Percent', format='.2f'))
        chart.height = 400
        chart.marginBottom = 100

        def get_data_for_graph():
            com = []
            rows = self.calculate_rows()
            for row in rows:
                com.append({"x": row[0], "y": row[1]['sort_key']})

            return [
                {
                    "key": "'Méthode de calcul: nbre de PPS avec le produit disponsible sur le nbre total de PPS visités de la période'",
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
