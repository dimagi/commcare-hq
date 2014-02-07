from django.utils.decorators import method_decorator
from corehq import toggles
from corehq.apps.reports.dispatcher import ReportDispatcher
from toggle.decorators import require_toggle


class AccountingAdminInterfaceDispatcher(ReportDispatcher):
    prefix = 'accounting_admin_interface'
    map_name = "ACCOUNTING_ADMIN_INTERFACES"

    @method_decorator(require_toggle(toggles.ACCOUNTING_PREVIEW))
    def dispatch(self, request, *args, **kwargs):
        return super(AccountingAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)
