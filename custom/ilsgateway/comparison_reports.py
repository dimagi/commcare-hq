from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.models import ILSGatewayConfig


class BaseComparisonReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    base_template = 'ilsgateway/base_template.html'
    hide_filters = True
    exportable = True

    @property
    def endpoint(self):
        return ILSGatewayEndpoint.from_config(ILSGatewayConfig.for_domain(self.domain))

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        if user and user.is_domain_admin(domain):
            return True
        return False
