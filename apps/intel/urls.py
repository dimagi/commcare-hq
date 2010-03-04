from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^intel/?$', 'intel.views_reports.all_mothers_report'),
    (r'^intel/all/?$', 'intel.views_reports.all_mothers_report'),
    (r'^intel/risk/?$', 'intel.views_reports.hi_risk_report'),
    (r'^intel/details/?$', 'intel.views_reports.mother_details'),
    
    (r'^intel/chart/?$', 'intel.views_charts.chart'),
)