from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.apps.userreports.views',
    url(r'^reports/edit/(?P<report_id>[\w-]+)/$', 'edit_report', name='edit_configurable_report'),
)
