from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^reports/$', 'reports.views.reports'),
    (r'^reports/(?P<domain_id>\d+)/custom/(?P<report_name>.*)/?$', 'reports.views.custom_report'),
    (r'^reports/(?P<case_id>\d+)/flat/?$', 'reports.views.case_flat'),
    (r'^reports/sql/(?P<report_id>\d+)/?$', 'reports.views.sql_report'),
    (r'^reports/sql/(?P<report_id>\d+)/csv/?$', 'reports.views.sql_report_csv'),
    (r'^reports/(?P<case_id>\d+)/csv/?$', 'reports.views.case_export_csv'),
    (r'^reports/(?P<case_id>\d+)/single/(?P<case_instance_id>.*)/?$', 'reports.views.single_case_view'),
    
)
