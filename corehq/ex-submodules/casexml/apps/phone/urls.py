from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    url(r'^restore/$', 'casexml.apps.phone.views.restore'),
    url(r'^single_case/(?P<case_id>\w+)/$', 'casexml.apps.phone.views.xml_for_case', name="single_case_xml"),
)

