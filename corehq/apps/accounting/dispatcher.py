from django.utils.decorators import method_decorator
from corehq import privileges
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.reports.dispatcher import ReportDispatcher
from django_prbac.decorators import requires_privilege_raise404


class AccountingAdminInterfaceDispatcher(ReportDispatcher):
    prefix = 'accounting_admin_interface'
    map_name = "ACCOUNTING_ADMIN_INTERFACES"

    @method_decorator(require_superuser)
    @method_decorator(requires_privilege_raise404(privileges.ACCOUNTING_ADMIN))
    def dispatch(self, request, *args, **kwargs):
        return super(AccountingAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)
