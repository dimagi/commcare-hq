from corehq.apps.domain.decorators import login_and_domain_required
from django.utils.decorators import method_decorator

from corehq.apps.reports.dispatcher import ReportDispatcher
from corehq.apps.enterprise.decorators import require_enterprise_admin
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.hqwebapp.views import not_found

class EnterpriseReportDispatcher(ReportDispatcher):
    prefix = 'enterprise_interface'
    map_name = "ENTERPRISE_INTERFACES"

    @method_decorator(login_and_domain_required)
    @method_decorator(require_enterprise_admin)
    def dispatch(self, request, *args, **kwargs):
        if BillingAccount._is_sms_billable_report_visible(args[0]):
            return super().dispatch(request, *args, **kwargs)
        return not_found(request)
