from corehq.apps.reports.standard.inspect import MapReport as BaseMapReport
from corehq.apps.reports.commtrack.psi_prototype import CommtrackReportMixin
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from django.conf import settings
import json

class StockStatusMapReport(BaseMapReport, CommtrackReportMixin):
    name = ugettext_noop("Stock Status (map)")
    slug = "stockstatus_map"
    hide_filters = True
    report_partial_path = "reports/partials/commtrack_maps.html"
    asynchronous = False

    @property
    def report_context(self):
        ctx = super(StockStatusMapReport, self).report_context
        ctx.update({
                'products': self.products,
            })
        return ctx
