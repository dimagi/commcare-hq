from corehq.apps.reports.commtrack.psi_prototype import CommtrackReportMixin
from corehq.apps.reports.standard.inspect import GenericMapReport
from django.utils.translation import ugettext_noop

class StockStatusMapReport(GenericMapReport, CommtrackReportMixin):
    name = ugettext_noop("Stock Status (map)")
    slug = "stockstatus_map"

    fields = ['corehq.apps.reports.fields.AsyncLocationField']

    data_source = {
        'adapter': 'report',
        'geo_column': 'geo',
        'report': 'corehq.apps.reports.commtrack.data_sources.StockStatusDataSource',
    }
    display_config = {}
