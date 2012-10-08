from dimagi.utils.decorators.memoized import memoized
from mvp.reports import MVPIndicatorReport

class MVISHealthCoordinatorReport(MVPIndicatorReport):
    """
        MVP Custom Report: MVIS Health Coordinator
    """
    fields = []
    slug = "health_coordinator"
    name = "MVIS Health Coordinator Report"
    report_template_path = "mvp/reports/health_coordinator.html"

    @property
    @memoized
    def indicators(self):
        indicators = [
            dict(
                title="Proportion of Under-5's with uncomplicated fever who recieved RDT test22"
            )
        ]

        return indicators



