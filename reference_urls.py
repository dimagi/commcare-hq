from django.conf.urls.defaults import patterns, include
#todo, django 1.6 defaults is removed

urlpatterns = patterns('',
                       (r'^refcase/', include('casexml.apps.case.urls')),
                       (r'^refphone/', include('casexml.apps.phone.urls')),
                       )
