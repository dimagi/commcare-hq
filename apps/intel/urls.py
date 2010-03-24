from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^intel/?$', 'intel.views.homepage'),
    (r'^intel/all/?$', 'intel.views.all_mothers_report'),
    (r'^intel/risk/?$', 'intel.views.hi_risk_report'),
    (r'^intel/details/?$', 'intel.views.mother_details'),
    
    (r'^intel/chart/?$', 'intel.views.chart'),
    
    (r'^intel/hq_chart/?$', 'intel.views.hq_chart'),
    (r'^intel/hq_risk/?$', 'intel.views.hq_risk'),
)