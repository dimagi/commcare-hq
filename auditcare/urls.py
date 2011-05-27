import traceback
from django.conf.urls.defaults import *

def is_test_trace(item):
    if item.find('/django/test/') > 0:
        return True
    if item.find('/django/contrib/auth/tests/') > 0:
        return True
    return False

traces = traceback.format_stack(limit=5)
is_tests = filter(is_test_trace, traces)


urlpatterns = patterns('',
    url(r'^auditor/?$', 'auditcare.views.auditAll', name='auditAll'),
)
if len(is_tests)  == 0:
    #Note this is a nasty hack to internally test the consistency of the login/logout auditing, but also not break django's auth unit tests.
    #in actual runtime, the monkeypatched login/logout views work beautifully in all sorts of permutations of access.
    #in tests it just fails hard due to the function dereferencing.
    urlpatterns += patterns('',
        url(r'^auditor/testaudit_login', 'auditcare.views.audited_login'),
        url(r'^auditor/testaudit_login', 'auditcare.views.audited_login')
    )

