from django.conf.urls.defaults import *

urlpatterns = patterns('custom.apps.crs_reports.views',
    url(r'^crs_custom_case_data/(?P<case_id>[\w\-]+)/(?P<module_name>[\w\-]+)/(?P<report_template>[\w\-]+)/(?P<report_slug>[\w\-]+)', "crs_details_report", name="crs_details_report"),
)