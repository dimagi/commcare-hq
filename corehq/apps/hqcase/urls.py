from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqcase.views',
    # stub urls
    (r'open_cases.json', 'open_cases_json'),
    (r'open_cases', 'open_cases'),
)