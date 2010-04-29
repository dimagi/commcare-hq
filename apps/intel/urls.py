from django.conf.urls.defaults import *

urlpatterns = patterns('intel.views',
    (r'^intel/?$', 'homepage'),
    (r'^intel/all\.?(?P<format>[a-zA-Z0-9\.].*)?/?$', 'report'),
    (r'^intel/risk\.?(?P<format>[a-zA-Z0-9\.].*)?/?$', 'report'),
    (r'^intel/details/?$', 'mother_details'),

    (r'^intel/record_visit/?$', 'record_visit'),
    
    (r'^intel/chart/?$', 'chart'),
    
    (r'^intel/hq_chart/?$', 'hq_chart'),
    (r'^intel/hq_risk/?$', 'hq_risk'),
)