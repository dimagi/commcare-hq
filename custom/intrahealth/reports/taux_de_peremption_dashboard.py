# coding=utf-8

import datetime

from django.utils.functional import cached_property

from corehq.apps.hqwebapp.decorators import use_nvd3
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import DateRangeFilter, ProgramsAndProductsFilter, YeksiNaaLocationFilter
from custom.intrahealth.sqldata import ExpirationRatePerProductData2
from dimagi.utils.dates import force_to_date


class TauxDePeremptionReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    slug = 'taux_de_peremption_report'
    comment = 'valeur péremption sur valeur totale'
    name = 'Taux de Péremption'
    default_rows = 10

    report_template_path = 'yeksi_naa/tabular_report.html'

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(TauxDePeremptionReport, self).decorator_dispatcher(request, *args, **kwargs)

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
        return ExpirationRatePerProductData2(config=self.config).headers

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
        rows = ExpirationRatePerProductData2(config=self.config).rows
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
                #-1 removes % symbol for cast to float
                try:
                    name = row[0]['html']
                    value = float(row[-1]['html'][:-1])
                except ValueError:
                    value = 0.0
                    name = "{}\n({})".format(name, "pas de données")
                finally:
                    com.append({"x": value, "y": value})

            return [
                {
                    "key": "valeur péremption sur valeur totale",
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
        config['products'] = ['product1', 'product2', 'product3']
        return config
