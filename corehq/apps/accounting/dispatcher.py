from corehq.apps.crud.dispatcher import BaseCRUDAdminInterfaceDispatcher
from corehq.apps.reports.dispatcher import datespan_default


class AccountingAdminInterfaceDispatcher(BaseCRUDAdminInterfaceDispatcher):
    prefix = 'accounting_admin_interface'
    map_name = "ACCOUNTING_ADMIN_INTERFACES"

    @datespan_default
    def dispatch(self, request, *args, **kwargs):
        return super(AccountingAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)


class SubscriptionAdminInterfaceDispatcher(BaseCRUDAdminInterfaceDispatcher):
    prefix = 'subscription_admin_interface'
    map_name = "SUBSCRIPTION_ADMIN_INTERFACES"

    @datespan_default
    def dispatch(self, request, *args, **kwargs):
        return super(SubscriptionAdminInterfaceDispatcher, self).dispatch(request, *args, **kwargs)
