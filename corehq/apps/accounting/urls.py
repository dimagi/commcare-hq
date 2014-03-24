from django.conf.urls.defaults import *
from corehq import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.views import *


urlpatterns = patterns('corehq.apps.accounting.views',
    url(r'^$', 'accounting_default', name='accounting_default'),
    url(r'^trigger_invoice/$', TriggerInvoiceView.as_view(),
        name=TriggerInvoiceView.urlname),
    url(r'^accounts/(\d+)/$', ManageBillingAccountView.as_view(), name=ManageBillingAccountView.urlname),
    url(r'^accounts/new/$', NewBillingAccountView.as_view(), name=NewBillingAccountView.urlname),
    url(r'^subscriptions/(\d+)/$', EditSubscriptionView.as_view(), name=EditSubscriptionView.urlname),
    url(r'^accounts/new_subscription/$', NewSubscriptionViewNoDefaultDomain.as_view(),
        name=NewSubscriptionViewNoDefaultDomain.urlname),
    url(r'^accounts/new_subscription/(\d+)/$', NewSubscriptionView.as_view(), name=NewSubscriptionView.urlname),
    url(r'^software_plans/new/$', NewSoftwarePlanView.as_view(), name=NewSoftwarePlanView.urlname),
    url(r'^software_plans/(\d+)/$', EditSoftwarePlanView.as_view(), name=EditSoftwarePlanView.urlname),
    url(r'^invoices/(\d+)/$', InvoiceSummaryView.as_view(),
        name=InvoiceSummaryView.urlname),
    url(AccountingAdminInterfaceDispatcher.pattern(), AccountingAdminInterfaceDispatcher.as_view(),
        name=AccountingAdminInterfaceDispatcher.name()),
    url(r'^pricing_table/(?P<product>[\w-]+)/(?P<locale>[\w-]+)/$', 'pricing_table_json', name='pricing_table_json'),
)
