from corehq.apps.crud.dispatcher import BaseCRUDAdminInterfaceDispatcher

class AccountingAdminInterfaceDispatcher(BaseCRUDAdminInterfaceDispatcher):
    prefix = 'accounting_admin_interface'
    map_name = "ACCOUNTING_ADMIN_INTERFACES"
