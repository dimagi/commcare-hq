from django.conf.urls.defaults import patterns, url, include
from django.views.generic.simple import direct_to_template

cases_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^list/$', 'case_list', name='cloudcare_case_list'),
    url(r'^view/(?P<case_id>[\w-]*)/$', 'view_case', name='cloudcare_view_case'),
)

urlpatterns = patterns('corehq.apps.cloudcare.views',
    url(r'^cases/', include(cases_urls)),
    url(r'^test/$', direct_to_template, {'template': 'cloudcare/test.html'}),
)