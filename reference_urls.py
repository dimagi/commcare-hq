from django.conf.urls.defaults import patterns, include

urlpatterns = patterns('',
                       (r'^refcase/', include('casexml.apps.case.urls')),
                       (r'^refphone/', include('casexml.apps.phone.urls')),
                       )
