from corehq.apps.reports.generic import GenericTabularReport
from mvp.reports import MVPIndicatorReport

class CHWManagerReport(GenericTabularReport, MVPIndicatorReport):
    slug = "chw_manager"
    name = "CHW Manager Report"

