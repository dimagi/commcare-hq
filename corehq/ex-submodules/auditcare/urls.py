from django.conf import settings
from django.conf.urls import url

from auditcare.utils import login_template, logout_template
from auditcare.views import (
    audited_login,
    audited_logout,
    audited_views,
    export_all,
)

urlpatterns = [
    url(r'^auditor/export/$', export_all, name='export_all_audits'),
    url(r'^auditor/views/$', audited_views, name='audit_views'),

    # directly overriding due to wrapped functions causing serious problems with tests
    url(r'^accounts/login/$', audited_login, {'template_name': login_template()}, name='auth_login'),
    url(r'^accounts/logout/$', audited_logout, {'template_name': logout_template()}, name='auth_logout'),
]

if settings.UNIT_TESTING:
    # Note this is a nasty hack to internally test the consistency of the
    # login/logout auditing, but also not break django's auth unit tests. in
    # actual runtime, the monkeypatched login/logout views work beautifully in
    # all sorts of permutations of access. in tests it just fails hard due to
    # the function dereferencing.
    urlpatterns += [
        url(r'^auditor/testaudit_login', audited_login),
        url(r'^auditor/testaudit_logout', audited_logout)
    ]
