from datetime import datetime, date
from itertools import chain

from dimagi.utils.logging import notify_exception

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from custom.inddex.fixtures import InddexFixtureError


class MultiTabularReport(DatespanMixin, CustomProjectReport, GenericTabularReport):
    base_template = 'inddex/report_base.html'  # The base report page
    report_template_path = 'inddex/multi_report.html'  # the async content
    exportable = True
    exportable_all = True
    export_only = False

    @property
    def data_providers(self):
        # data providers should supply a title, slug, headers, and rows
        return []

    @property
    def report_context(self):

        def _to_context_dict(data_provider):
            return {
                'title': data_provider.title,
                'slug': data_provider.slug,
                'headers': DataTablesHeader(
                    *(DataTablesColumn(header) for header in data_provider.headers),
                ),
                'rows': list(data_provider.rows),
            }

        context = {
            'name': self.name,
            'export_only': self.export_only
        }
        if not self.export_only and not self.needs_filters:
            try:
                context['data_providers'] = list(map(_to_context_dict, self.data_providers))
            except InddexFixtureError as e:
                context['data_providers'] = []
                context['fixture_error'] = str(e)
                notify_exception(self.request, str(e))
        return context

    @property
    def export_table(self):
        return [
            [dp.slug, chain([dp.headers], dp.rows)]
            for dp in self.data_providers
        ]


def na_for_None(val):
    return 'n/a' if val is None else val


def _format_val(val):
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, bool):
        return "yes" if val else "no"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return f"{val:.5g}"
    if val is None:
        return ''
    return val


def format_row(row):
    return [_format_val(val) for val in row]
