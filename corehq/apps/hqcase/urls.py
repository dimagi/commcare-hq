from django.conf.urls import *

urlpatterns = patterns('corehq.apps.hqcase.views',
    # for load testing
    url(r'explode/', 'explode_cases', name='hqcase_explode_cases')
)
