from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin


class MultiTabularReport(DatespanMixin, CustomProjectReport, GenericTabularReport):
    report_template_path = 'inddex/multi_report.html'
    exportable = True
    export_only = False

    @property
    def data_providers(self):
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
                'headers': data_provider.headers,
                'rows': data_provider.rows,
            } for data_provider in self.data_providers]
        return context

    @property
    def export_table(self):
        return [
            [dp.slug, [dp.headers] + dp.rows]
            for dp in self.data_providers
        ]
