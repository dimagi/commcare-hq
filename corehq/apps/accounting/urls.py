from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.views import (
    AccountingSingleOptionResponseView,
    EditSoftwarePlanView,
    EditSubscriptionView,
    InvoiceSummaryView,
    ManageAccountingAdminsView,
    ManageBillingAccountView,
    NewBillingAccountView,
    NewSoftwarePlanView,
    NewSubscriptionView,
    NewSubscriptionViewNoDefaultDomain,
    TestRenewalEmailView,
    TriggerBookkeeperEmailView,
    TriggerInvoiceView,
    TriggerCustomerInvoiceView,
    ViewSoftwarePlanVersionView,
    WireInvoiceSummaryView,
    CustomerInvoiceSummaryView,
    accounting_default,
    enterprise_dashboard,
    enterprise_dashboard_download,
    enterprise_dashboard_email,
    enterprise_dashboard_total,
    CustomerInvoicePdfView
)


urlpatterns = [
    url(r'^$', accounting_default, name='accounting_default'),
    url(r'^trigger_invoice/$', TriggerInvoiceView.as_view(),
        name=TriggerInvoiceView.urlname),
    url(r'^trigger_customer_invoice/$', TriggerCustomerInvoiceView.as_view(),
        name=TriggerCustomerInvoiceView.urlname),
    url(r'^single_option_filter/$', AccountingSingleOptionResponseView.as_view(),
        name=AccountingSingleOptionResponseView.urlname),
    url(r'^trigger_email/$', TriggerBookkeeperEmailView.as_view(),
        name=TriggerBookkeeperEmailView.urlname),
    url(r'^test_reminders/$', TestRenewalEmailView.as_view(),
        name=TestRenewalEmailView.urlname),
    url(r'^manage_admins/$', ManageAccountingAdminsView.as_view(),
        name=ManageAccountingAdminsView.urlname),
    url(r'^accounts/(\d+)/$', ManageBillingAccountView.as_view(), name=ManageBillingAccountView.urlname),
    url(r'^accounts/new/$', NewBillingAccountView.as_view(), name=NewBillingAccountView.urlname),
    url(r'^subscriptions/(\d+)/$', EditSubscriptionView.as_view(), name=EditSubscriptionView.urlname),
    url(r'^accounts/new_subscription/$', NewSubscriptionViewNoDefaultDomain.as_view(),
        name=NewSubscriptionViewNoDefaultDomain.urlname),
    url(r'^accounts/new_subscription/(\d+)/$', NewSubscriptionView.as_view(), name=NewSubscriptionView.urlname),
    url(r'^software_plans/new/$', NewSoftwarePlanView.as_view(), name=NewSoftwarePlanView.urlname),
    url(r'^software_plans/(\d+)/$', EditSoftwarePlanView.as_view(), name=EditSoftwarePlanView.urlname),
    url(r'^software_plan_versions/(\d+)/(\d+)/$', ViewSoftwarePlanVersionView.as_view(), name=ViewSoftwarePlanVersionView.urlname),
    url(r'^invoices/(\d+)/$', InvoiceSummaryView.as_view(), name=InvoiceSummaryView.urlname),
    url(r'^wire_invoices/(\d+)/$', WireInvoiceSummaryView.as_view(), name=WireInvoiceSummaryView.urlname),
    url(r'^customer_invoices/(\d+)/$', CustomerInvoiceSummaryView.as_view(),
        name=CustomerInvoiceSummaryView.urlname),
    url(r'^customer_invoices/(?P<statement_id>[\w-]+).pdf$', CustomerInvoicePdfView.as_view(),
        name=CustomerInvoicePdfView.urlname),
    url(AccountingAdminInterfaceDispatcher.pattern(), AccountingAdminInterfaceDispatcher.as_view(),
        name=AccountingAdminInterfaceDispatcher.name()),
]

domain_specific = [
    url(r'^dashboard/$', enterprise_dashboard, name='enterprise_dashboard'),
    url(r'^dashboard/(?P<slug>[^/]*)/download/(?P<export_hash>[\w\-]+)/$', enterprise_dashboard_download,
        name='enterprise_dashboard_download'),
    url(r'^dashboard/(?P<slug>[^/]*)/email/$', enterprise_dashboard_email,
        name='enterprise_dashboard_email'),
    url(r'^dashboard/(?P<slug>[^/]*)/total/$', enterprise_dashboard_total,
        name='enterprise_dashboard_total'),
]
