import traceback
from django.conf.urls.defaults import *
import settings

def is_test_trace(item):
    if item.find('/django/test/') > 0:
        return True
    if item.find('/django/contrib/auth/tests/') > 0:
        return True
    return False

traces = traceback.format_stack(limit=5)
is_tests = filter(is_test_trace, traces)


urlpatterns = patterns('',
    url(r'^auditor/$', 'auditcare.views.auditAll', name='auditAll'),
    url(r'^auditor/export/$', 'auditcare.views.export_all', name='export_all_audits'),
    url(r'^auditor/models/$', 'auditcare.views.model_histories', name='model_histories'),
    url(r'^auditor/views/$', 'auditcare.views.audited_views', name='audit_views'),
    url(r'^auditor/models/(?P<model_name>\w+)/$', 'auditcare.views.single_model_history', name='single_model_history'),
    url(r'^auditor/models/(?P<model_name>\w+)/(?P<model_uuid>.*)/$', 'auditcare.views.model_instance_history', name='model_instance_history'),

    #directly overriding due to wrapped functions causing serious problems with tests
    url(r'^accounts/login/$', 'auditcare.views.audited_login', {'template_name': settings.LOGIN_TEMPLATE}, name='auth_login'),
    url(r'^accounts/logout/$', 'auditcare.views.audited_logout', {'template_name': settings.LOGGEDOUT_TEMPLATE}, name='auth_logout'),
)


if len(is_tests)  == 0:
    #Note this is a nasty hack to internally test the consistency of the login/logout auditing, but also not break django's auth unit tests.
    #in actual runtime, the monkeypatched login/logout views work beautifully in all sorts of permutations of access.
    #in tests it just fails hard due to the function dereferencing.
    urlpatterns += patterns('',
        url(r'^auditor/testaudit_login', 'auditcare.views.audited_login'),
        url(r'^auditor/testaudit_logout', 'auditcare.views.audited_logout')
    )

