from datetime import datetime
from itertools import chain

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin


class MultiTabularReport(DatespanMixin, CustomProjectReport, GenericTabularReport):
    report_template_path = 'inddex/multi_report.html'
    exportable = True
    exportable_all = True
    export_only = False

    @property
    def data_providers(self):
        # data providers should supply a title, slug, headers, and rows
        return []

    @property
    def report_context(self):
        context = {
            'name': self.name,
            'export_only': self.export_only
        }
        if not self.needs_filters:
            context['data_providers'] = [{
                'title': data_provider.title,
                'slug': data_provider.slug,
                'headers': DataTablesHeader(
                    *(DataTablesColumn(header) for header in data_provider.headers),
                ),
                'rows': data_provider.rows,
            } for data_provider in self.data_providers]
        return context

    @property
    def export_table(self):
        return [
            [dp.slug, chain([dp.headers], dp.rows)]
            for dp in self.data_providers
        ]


def format_val(val):
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, bool):
        return "yes" if val else "no"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return str(int(val)) if val.is_integer() else str(val)
    if val is None:
        return ''
    return val
