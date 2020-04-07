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
        return {
            'reports': [self._get_report_context(dp) for dp in self.data_providers],
            'name': self.name,
            'export_only': self.export_only
        }

    def _get_report_context(self, data_provider):
        filters_selected = not self.needs_filters
        return {
            'report_table': {
                'title': data_provider.title,
                'slug': data_provider.slug,
                'headers': data_provider.headers if filters_selected else [],
                'rows': data_provider.rows if filters_selected else [],
            }
        }

    @property
    def export_table(self):
        return [
            [dp.slug, [dp.headers] + dp.rows]
            for dp in self.data_providers
        ]
