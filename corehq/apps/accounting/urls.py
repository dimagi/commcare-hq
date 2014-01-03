from django.conf.urls.defaults import *
from corehq import AccountingInterface2, AccountingAdminInterfaceDispatcher


urlpatterns = patterns('corehq.apps.accounting.views',
    url(r'^view_billing_accounts/$', 'view_billing_accounts', name='view_billing_accounts'),
    url(r'^accounting_default/$', 'accounting_default', name='accounting_default'),
    url(AccountingAdminInterfaceDispatcher.pattern(), AccountingAdminInterfaceDispatcher.as_view(),
        name=AccountingAdminInterfaceDispatcher.name())
)
