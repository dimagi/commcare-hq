from django.conf.urls import url

from corehq.apps.enterprise.views import (
    delete_domain_permission_mirror,
    edit_enterprise_settings,
    enterprise_dashboard,
    enterprise_dashboard_download,
    enterprise_dashboard_email,
    enterprise_dashboard_total,
    enterprise_permissions,
    enterprise_settings,
    update_enterprise_permissions_source_domain,
)
from corehq.apps.enterprise.views import EnterpriseBillingStatementsView
from corehq.apps.sso.views.enterprise_admin import (
    ManageSSOEnterpriseView,
    EditIdentityProviderEnterpriseView,
)

domain_specific = [
    url(r'^dashboard/$', enterprise_dashboard, name='enterprise_dashboard'),
    url(r'^dashboard/(?P<slug>[^/]*)/download/(?P<export_hash>[\w\-]+)/$', enterprise_dashboard_download,
        name='enterprise_dashboard_download'),
    url(r'^dashboard/(?P<slug>[^/]*)/email/$', enterprise_dashboard_email,
        name='enterprise_dashboard_email'),
    url(r'^dashboard/(?P<slug>[^/]*)/total/$', enterprise_dashboard_total,
        name='enterprise_dashboard_total'),
    url(r'^permissions/$', enterprise_permissions, name="enterprise_permissions"),
    url(r'^permissions/delete/(?P<mirror>[ \w-]+)/$', delete_domain_permission_mirror,
        name='delete_domain_permission_mirror'),
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
]
