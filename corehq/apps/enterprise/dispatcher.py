from django.utils.decorators import method_decorator

from corehq.apps.reports.dispatcher import ReportDispatcher
from corehq.apps.enterprise.decorators import require_enterprise_admin


class EnterpriseInterfaceDispatcher(ReportDispatcher):
    prefix = 'enterprise_interface'
    map_name = "ENTERPRISE_INTERFACES"

    @method_decorator(require_enterprise_admin)
    def dispatch(self, request, *args, **kwargs):
        return super(EnterpriseInterfaceDispatcher, self).dispatch(request, *args, **kwargs)
