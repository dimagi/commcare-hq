from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.crs_reports.views',
    url(r'^(?P<case_id>[\w\-]+)/(?P<module_name>[\w\-]+)/(?P<report_template>[\w\-]+)/(?P<report_slug>[\w\-]+)', "case_details_report", name="case_details_report"),
)