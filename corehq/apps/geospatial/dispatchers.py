from corehq import toggles
from corehq.apps.reports.dispatcher import (
    ReportDispatcher,
    cls_to_view_login_and_domain,
)


class CaseManagementMapDispatcher(ReportDispatcher):
    prefix = 'geospatial'
    map_name = 'GEOSPATIAL_MAP'

    @cls_to_view_login_and_domain
    def dispatch(self, request, *args, **kwargs):
        return super(CaseManagementMapDispatcher, self).dispatch(request, *args, **kwargs)

    def permissions_check(self, report, request, domain=None, is_navigation_check=False):
        return toggles.GEOSPATIAL.enabled(domain)
