from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^reports/$', 'reports.views.reports'),
    (r'^xforms/reports/(?P<case_id>\d+)/?$', 'reports.views.case_data'),
    (r'^xforms/reports/(?P<case_id>\d+)/csv/?$', 'reports.views.case_export_csv'),
    (r'^xforms/reports/(?P<domain_id>\d+)/custom/(?P<report_name>.*)/?$', 'reports.views.custom_report')
)
