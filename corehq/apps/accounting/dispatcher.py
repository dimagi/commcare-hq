from corehq.apps.crud.dispatcher import BaseCRUDAdminInterfaceDispatcher
from corehq.apps.reports.dispatcher import datespan_default


class AccountingAdminInterfaceDispatcher(BaseCRUDAdminInterfaceDispatcher):
    prefix = 'accounting_admin_interface'
    map_name = "ACCOUNTING_ADMIN_INTERFACES"
