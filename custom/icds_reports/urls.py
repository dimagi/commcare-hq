from django.conf.urls import patterns, url

from custom.icds_reports.views import tableau

urlpatterns = patterns('custom.icds_reports.views',
    url(r'^tableau/(?P<workbook>\w+)/(?P<worksheet>\w+)$', tableau, name='icds_tableau'),
)
