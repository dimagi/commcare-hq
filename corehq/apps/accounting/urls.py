from django.conf.urls.defaults import *
from corehq import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.views import *


urlpatterns = patterns('corehq.apps.accounting.views',
    url(r'^accounting_default/$', 'accounting_default', name='accounting_default'),
    url(r'^accounts/(\d+)/$', ManageBillingAccountView.as_view(), name=ManageBillingAccountView.urlname),
    url(r'^accounts/new/', NewBillingAccountView.as_view(), name=NewBillingAccountView.urlname),
    url(r'^subscriptions/(\d+)/', EditSubscriptionView.as_view(), name=EditSubscriptionView.urlname),
    url(r'^accounts/new_subscription/(\d+)/', NewSubscriptionView.as_view(), name=NewSubscriptionView.urlname),
    url(AccountingAdminInterfaceDispatcher.pattern(), AccountingAdminInterfaceDispatcher.as_view(),
        name=AccountingAdminInterfaceDispatcher.name()),
)
