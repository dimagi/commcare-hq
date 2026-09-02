from django.utils.decorators import method_decorator

from corehq.apps.accounting.decorators import accounting_admin_required
from corehq.apps.reports.dispatcher import ReportDispatcher


class AccountingAdminInterfaceDispatcher(ReportDispatcher):
    prefix = 'accounting_admin_interface'
    map_name = "ACCOUNTING_ADMIN_INTERFACES"

    @method_decorator(accounting_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(AccountingAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)
