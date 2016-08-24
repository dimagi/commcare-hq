from django.conf.urls import patterns, url

urlpatterns = patterns('custom.icds_reports.views',
    url(r'^tableau/(?P<workbook>\w+)/(?P<worksheet>\w+)$', 'tableau', name='icds_tableau'),
)
