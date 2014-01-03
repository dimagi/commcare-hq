from django.conf.urls.defaults import *
from corehq import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.dispatcher import SubscriptionAdminInterfaceDispatcher


urlpatterns = patterns('corehq.apps.accounting.views',
    url(r'^view_billing_accounts/$', 'view_billing_accounts', name='view_billing_accounts'),
    url(r'^accounting_default/$', 'accounting_default', name='accounting_default'),
    url(r'^accounts/(\d+)/', 'manage_billing_account', name='manage_billing_account'),
    url(AccountingAdminInterfaceDispatcher.pattern(), AccountingAdminInterfaceDispatcher.as_view(),
        name=AccountingAdminInterfaceDispatcher.name()),
    url(SubscriptionAdminInterfaceDispatcher.pattern(), SubscriptionAdminInterfaceDispatcher.as_view(),
        name=SubscriptionAdminInterfaceDispatcher.name()),
)
