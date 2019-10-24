import datetime

from django.utils.functional import cached_property

from corehq.apps.hqwebapp.decorators import use_nvd3
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.graph_models import Axis
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport, DatespanMixin
from custom.intrahealth.filters import DateRangeFilter, ProgramsAndProductsFilter, YeksiNaaLocationFilter
from custom.intrahealth.sqldata import LossRatePerProductData2
from dimagi.utils.dates import force_to_date

from custom.intrahealth.utils import PNAMultiBarChart


class TauxDePerteReport(CustomProjectReport, DatespanMixin, ProjectReportParametersMixin):
    slug = 'taux_de_perte_par_produit_report'
    comment = 'Taux de Perte (hors péremption)'
    name = 'Taux de Perte par Produit'
    default_rows = 10
    exportable = True

    report_template_path = 'yeksi_naa/tabular_report.html'

    @property
    def export_table(self):
        report = [
            [
                self.name,
                [],
            ]
        ]
        headers = [x.html for x in self.headers]
        headers.pop()
        rows = self.calculate_rows()
        report[0][1].append(headers)

        for row in rows:
            location_name = row[0]['html']
            row_to_return = [location_name]

            rows_length = len(row) - 1
            for r in range(1, rows_length):
                value = row[r]['html']
                row_to_return.append(value)

            report[0][1].append(row_to_return)

        return report

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(TauxDePerteReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def fields(self):
        return [DateRangeFilter, ProgramsAndProductsFilter, YeksiNaaLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @property
    def report_context(self):
        if not self.needs_filters:
            return {
                'report': self.get_report_context(),
                'charts': self.charts,
                'title': self.name
            }
        return {}

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
                return 'Region'
            elif location_type == 'district':
                return 'District'
            elif location_type == 'pps':
                return 'PPS'
        else:
            pass

    @property
    def headers(self):
        return LossRatePerProductData2(config=self.config).headers

    def get_report_context(self):
        if self.needs_filters:
            headers = []
            rows = []
        else:
            rows = self.calculate_rows()
            headers = self.headers

        context = {
            'report_table': {
                'title': self.name,
                'slug': self.slug,
                'comment': self.comment,
                'headers': headers,
                'rows': rows,
                'default_rows': self.default_rows,
            }
        }

        return context

    def calculate_rows(self, for_chart=False):
        rows = LossRatePerProductData2(config=self.config).rows(for_chart=for_chart)
        return rows

    @property
    def charts(self):
        chart = PNAMultiBarChart(None, Axis('Location'), Axis('Percent', format='.2f'))
        chart.height = 550
        chart.marginBottom = 150
        chart.rotateLabels = -45
        chart.showControls = False
        chart.forceY = [0, 100]

        def get_data_for_graph():
            com = []
            sorted_products, rows = self.calculate_rows(for_chart=True)
            for product in sorted_products:
                y = float(rows[product]['percent'][:-1])
                com.append({"x": product, "y": y})

            return [
                {
                    'key':
                        'Méthode de calcul: Nombre total de produits PNA perdus '
                        '(non compris les produits périmés) sur PNA stock final',
                    'values': com
                },
            ]

        chart.data = get_data_for_graph()
        return [chart]

    @property
    def config(self):
        config = {
            'domain': self.domain,
        }
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
        config['products'] = self.request.GET.get('products')
        config['product_product'] = self.request.GET.get('product_product')
        config['selected_location'] = self.request.GET.get('location_id')

        if self.selected_location_type == "PPS":
            config['pps_id'] = self.request.GET.get('location_id')
        elif self.selected_location_type == "District":
            config['district_id'] = self.request.GET.get('location_id')
        elif self.selected_location_type == "Region":
            config['region_id'] = self.request.GET.get('location_id')

        return config
