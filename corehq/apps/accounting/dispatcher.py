from corehq.apps.crud.dispatcher import BaseCRUDAdminInterfaceDispatcher


class AccountingAdminInterfaceDispatcher(BaseCRUDAdminInterfaceDispatcher):
    prefix = 'accounting_admin_interface'
    map_name = "ACCOUNTING_ADMIN_INTERFACES"


class SubscriptionAdminInterfaceDispatcher(BaseCRUDAdminInterfaceDispatcher):
    prefix = 'subscription_admin_interface'
    map_name = "SUBSCRIPTION_ADMIN_INTERFACES"
