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
    comment = 'test comment change me later'
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
        # TODO: needs further implementation
        return DataTablesHeader(
            DataTablesColumn(self.selected_location_type),
            DataTablesColumn(
                'Méthode de calcul: nbre de PPS avec le produit disponsible sur le nbre total de PPS visités de la période'
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
        stocks = TauxDeRuptureRateData(config=self.config).rows

        def to_report_row(s):
            loc_type = self.selected_location_type.lower()
            stocks_list = []
            stocks_to_return = []

            for stock in s:
                data_dict = {
                    'location_name': stock['{}_name'.format(loc_type)],
                    'product_available_in_ppses': 0,
                    'number_of_ppses': 0,
                }

                length = len(stocks_list)
                if not stocks_list:
                    data_dict['product_available_in_ppses'] = 1 if stock['product_is_outstock'] == 1 else 0
                    data_dict['number_of_ppses'] = 1
                    stocks_list.append(data_dict)
                else:
                    for r in range(0, length):
                        location_name = stocks_list[r]['location_name']
                        if stock['{}_name'.format(loc_type)] == location_name:
                            if stock['product_is_outstock'] == 1:
                                stocks_list[r]['product_available_in_ppses'] += 1
                            stocks_list[r]['number_of_ppses'] += 1
                        else:
                            if r == len(stocks_list) - 1:
                                data_dict['product_available_in_ppses'] = 1 if stock['product_is_outstock'] == 1 else 0
                                data_dict['number_of_ppses'] = 1
                                stocks_list.append(data_dict)

            for stock in stocks_list:
                amount_of_products = stock['product_available_in_ppses']
                amount_of_ppses = stock['number_of_ppses']
                percent = (amount_of_products / float(amount_of_ppses)) * 100 \
                    if amount_of_ppses != 0 else 0
                stocks_to_return.append([
                    stock['location_name'],
                    {
                        'html': '{:.2f} %'.format(percent),
                        'sort_key': percent
                    }
                ])

            return stocks_to_return

        rows = to_report_row(stocks)
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
