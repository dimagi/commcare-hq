from django.conf.urls.defaults import *

urlpatterns = patterns('casexml.apps.case.views',
    # stub urls
    (r'open_cases.json', 'open_cases_json'),
    (r'open_cases', 'open_cases'),
)