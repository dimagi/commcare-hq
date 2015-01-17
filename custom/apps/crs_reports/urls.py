from django.conf.urls import *

urlpatterns = patterns('custom.apps.crs_reports.views',
    url(r'^crs_custom_case_data/(?P<case_id>[\w\-]+)/(?P<report_slug>[\w\-]+)$', "crs_details_report", name="crs_details_report"),
    url(r'^crs_custom_case_data/(?P<case_id>[\w\-]+)/(?P<report_slug>[\w\-]+)/to_pdf', "render_to_pdf", name="render_to_pdf"),
)