from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^reports/$', 'reports.views.reports'),
    (r'^reports/(?P<domain_id>\d+)/chws/(?P<chw_id>[a-zA-Z0-9\s\/\.]+)?enddate=(?P<enddate>[0-9\/]+)&startdate_active=(?P<active>[0-9\/]+)?$', 'reports.views.individual_chw'),
    (r'^reports/provider_summary/?$', 'reports.views.sum_provider'),
    (r'^reports/sum_ward/?$', 'reports.views.sum_ward'),
    (r'^reports/hbc_monthly_sum/?$', 'reports.views.hbc_monthly_sum'),
    (r'^reports/select_provider/?$', 'reports.views.select_prov'),
    (r'^reports/ward_csv/(?P<month>[0-9]+)/(?P<year>[0-9]+)/(?P<ward>.*)/?$', 'reports.views.ward_sum_csv'),
    (r'^reports/ward_pdf/(?P<month>[0-9]+)/(?P<year>[0-9]+)/(?P<ward>.*)/?$', 'reports.views.ward_sum_pdf'),
    (r'^reports/provider_csv/(?P<chw_id>.*)/(?P<month>[0-9]+)/(?P<year>[0-9]+)/?$', 'reports.views.sum_prov_csv'),
    (r'^reports/provider_pdf/(?P<chw_id>.*)/(?P<month>[0-9]+)/(?P<year>[0-9]+)/?$', 'reports.views.sum_prov_pdf'),
    (r'^reports/hbc_csv/(?P<month>[0-9]+)/(?P<year>[0-9]+)/(?P<ward>.*)/?$', 'reports.views.hbc_sum_csv'),
    (r'^reports/hbc_pdf/(?P<month>[0-9]+)/(?P<year>[0-9]+)/(?P<ward>.*)/?$', 'reports.views.hbc_sum_pdf'),
    (r'^reports/(?P<domain_id>\d+)/custom/(?P<report_name>.*)/?$', 'reports.views.custom_report'),
    (r'^reports/(?P<case_id>\d+)/flat/?$', 'reports.views.case_flat'),
    (r'^reports/sql/(?P<report_id>\d+)/?$', 'reports.views.sql_report'),
    (r'^reports/sql/(?P<report_id>\d+)/csv/?$', 'reports.views.sql_report_csv'),
    (r'^reports/(?P<case_id>\d+)/csv/?$', 'reports.views.case_export_csv'),
    (r'^reports/(?P<case_id>\d+)/single/(?P<case_instance_id>.*)/?$', 'reports.views.single_case_view'),
    
)