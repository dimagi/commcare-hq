from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^intel/?$', 'intel.views_reports.default_report'),
    (r'^intel/all/?$', 'intel.views_reports.default_report'),
    (r'^intel/risk/?$', 'intel.views_reports.hi_risk_report'),
    
    (r'^intel/chart/?$', 'intel.views_charts.chart'),
)