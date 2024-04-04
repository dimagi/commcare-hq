from corehq.apps.enterprise.dispatcher import EnterpriseReportDispatcher
from django.urls import include, re_path as url

from corehq.apps.enterprise.views import (
    add_enterprise_permissions_domain,
    disable_enterprise_permissions,
    edit_enterprise_settings,
    enterprise_dashboard,
    enterprise_dashboard_download,
    enterprise_dashboard_email,
    enterprise_dashboard_total,
    enterprise_permissions,
    enterprise_settings,
    remove_enterprise_permissions_domain,
    update_enterprise_permissions_source_domain,
    ManageEnterpriseMobileWorkersView,
)
from corehq.apps.enterprise.views import EnterpriseBillingStatementsView
from corehq.apps.sso.views.enterprise_admin import (
    ManageSSOEnterpriseView,
    EditIdentityProviderEnterpriseView,
)

report_urls = [
    EnterpriseReportDispatcher.url_pattern(),
]

domain_specific = [
    url(r'^dashboard/$', enterprise_dashboard, name='enterprise_dashboard'),
    url(r'^dashboard/(?P<slug>[^/]*)/download/(?P<export_hash>[\w\-]+)/$', enterprise_dashboard_download,
        name='enterprise_dashboard_download'),
    url(r'^dashboard/(?P<slug>[^/]*)/email/$', enterprise_dashboard_email,
        name='enterprise_dashboard_email'),
    url(r'^dashboard/(?P<slug>[^/]*)/total/$', enterprise_dashboard_total,
        name='enterprise_dashboard_total'),
    url(r'^permissions/$', enterprise_permissions, name="enterprise_permissions"),
    url(r'^permissions/disable/$', disable_enterprise_permissions, name="disable_enterprise_permissions"),
    url(r'^permissions/add/(?P<target_domain>[ \w-]+)/$', add_enterprise_permissions_domain,
        name='add_enterprise_permissions_domain'),
    url(r'^permissions/remove/(?P<target_domain>[ \w-]+)/$', remove_enterprise_permissions_domain,
        name='remove_enterprise_permissions_domain'),
    url(r'^permissions/source/$', update_enterprise_permissions_source_domain,
        name='update_enterprise_permissions_source_domain'),
    url(r'^settings/$', enterprise_settings, name='enterprise_settings'),
    url(r'^settings/edit/$', edit_enterprise_settings, name='edit_enterprise_settings'),
    url(r'^billing_statements/$', EnterpriseBillingStatementsView.as_view(),
        name=EnterpriseBillingStatementsView.urlname),
    url(r'^sso/$', ManageSSOEnterpriseView.as_view(),
        name=ManageSSOEnterpriseView.urlname),
    url(r'^sso/(?P<idp_slug>[^/]*)/$', EditIdentityProviderEnterpriseView.as_view(),
        name=EditIdentityProviderEnterpriseView.urlname),
    url(r'^mobile_workers/$', ManageEnterpriseMobileWorkersView.as_view(),
        name=ManageEnterpriseMobileWorkersView.urlname),

    url(r'^reports/', include(report_urls)),
]
