import datetime

from django.utils.functional import cached_property

from corehq.apps.reports.datatables import DataTablesColumn
from custom.intrahealth.filters import DateRangeFilter, RecapPassageTwoProgramFilter, \
    YeksiRecapPassageNaaLocationFilter
from custom.intrahealth.reports.utils import YeksiNaaMonthYearMixin
from custom.intrahealth.sqldata import RecapPassageTwoTables
from custom.intrahealth.reports.tableu_de_board_report_v2 import MultiReport
from dimagi.utils.dates import force_to_date


class RecapPassageTwoReport(YeksiNaaMonthYearMixin, MultiReport):
    slug = 'recap_passage_2'
    comment = 'recap passage 2'
    name = 'Recap Passage 2'
    title = "Recap Passage 2"
    default_rows = 10
    exportable = True

    report_template_path = "intrahealth/multi_report.html"

    @property
    def export_format(self):
        return 'xlsx'

    @property
    def export_table(self):
        report = []

        table_names = ['Recapitulatif Facturation', 'Consommations Facturables',
                       'Consommation Réelle', 'Livraison Total Effectuées', 'Stock Disponible Utilisable']
        table_provider = RecapPassageTwoTables(config=self.config)
        data = [
            table_provider.sumup_context,
            table_provider.billed_consumption_context,
            table_provider.actual_consumption_context,
            table_provider.amt_delivered_convenience_context,
            table_provider.display_total_stock_context,
        ]

        for table in data:
            headers = []
            for table_header in table['headers']:
                if isinstance(table_header, DataTablesColumn):
                    headers.append(table_header.html)
                else:
                    headers.append(table_header)

            rows = [headers]
            for table_content in table['rows']:
                next_export_row = []
                for cell in table_content:
                    if isinstance(cell, dict):
                        next_export_row.append(cell['html'])
                    else:
                        next_export_row.append(cell)

                rows.append(next_export_row)
            next_report = [table_names.pop(0), rows]
            report.append(next_report)

        return report

    @property
    def fields(self):
        return [DateRangeFilter, RecapPassageTwoProgramFilter, YeksiRecapPassageNaaLocationFilter]

    @cached_property
    def rendered_report_title(self):
        return self.name

    @cached_property
    def data_providers(self):
        table_provider = RecapPassageTwoTables(config=self.config)
        return [
            table_provider.sumup_context,
            table_provider.billed_consumption_context,
            table_provider.actual_consumption_context,
            table_provider.amt_delivered_convenience_context,
            table_provider.display_total_stock_context,
        ]

    def get_report_context(self, table_context):
        self.data_source = table_context
        if self.needs_filters:
            context = {
                'report_table': {
                    'rows': [],
                    'headers': []
                }
            }
        else:
            context = {
                'report_table': table_context
            }
        return context

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
        config['product_program'] = self.request.GET.get('program')
        config['selected_location'] = self.request.GET.get('location_id')
        return config
