from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.domain.models import Domain

class CommtrackReportMixin(ProjectReport):
    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        domain = Domain.get_by_name(kwargs['domain'])
        return domain.commtrack_enabled
    
class VisitReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Visit Report'
    slug = 'visits'

class SalesAndConsumptionReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Sales and Consumption Report'
    slug = 'sales_consumption'

