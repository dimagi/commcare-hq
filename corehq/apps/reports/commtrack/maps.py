from corehq.apps.reports.standard.inspect import MapReport as BaseMapReport
from corehq.apps.reports.commtrack.psi_prototype import CommtrackReportMixin
from django.utils.translation import ugettext_noop

class StockStatusMapReport(CommtrackReportMixin, BaseMapReport):
    name = ugettext_noop("Stock Status (map)")
    slug = "stockstatus_map"
    hide_filters = True
    report_partial_path = "reports/partials/commtrack_maps.html"
    asynchronous = False

    _config = {'case_types': [
            {
                "case_type": "supply-point-product",
                "display_name": "Supply Point",
                "fields": [
                    {
                        "field": "stock_category",
                        "display_name": "Stock Status",
                        "type": "enum",
                        "values": [
                            {"label": "Stock-out",      "value": "stockout",   "color": "#f00"},
                            {"label": "Understocked",   "value": "understock", "color": "#ff0"},
                            {"label": "Adequate Stock", "value": "adequate",   "color": "#0f0"},
                            {"label": "Overstocked",    "value": "overstock",  "color": "#80f"},
                            {"label": "No data",        "value": "nodata",     "color": "#888"},
                        ],
                    },
                ]
            }
        ]}

    @property
    def config(self):
        return self._config or self.get_config(self.domain)
    
    @property
    def report_context(self):
        ctx = super(StockStatusMapReport, self).report_context
        ctx.update({
                'products': self.products,
            })
        return ctx
