from corehq import toggles
from corehq.apps.reports.dispatcher import (
    ReportDispatcher,
    cls_to_view_login_and_domain,
)
from django.utils.decorators import method_decorator


@method_decorator(toggles.MICROPLANNING.required_decorator(), name='dispatch')
class CaseManagementMapDispatcher(ReportDispatcher):
    prefix = 'microplanning'
    map_name = 'GEOSPATIAL_MAP'

    @cls_to_view_login_and_domain
    def dispatch(self, request, *args, **kwargs):
        return super(CaseManagementMapDispatcher, self).dispatch(request, *args, **kwargs)
