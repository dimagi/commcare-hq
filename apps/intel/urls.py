from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^intel/?$', 'intel.views.all_mothers_report'),
    (r'^intel/all/?$', 'intel.views.all_mothers_report'),
    (r'^intel/risk/?$', 'intel.views.hi_risk_report'),
    (r'^intel/details/?$', 'intel.views.mother_details'),
    
    (r'^intel/chart/?$', 'intel.views.chart'),
)