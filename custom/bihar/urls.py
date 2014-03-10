from django.conf.urls.defaults import *

urlpatterns = patterns('custom.bihar.views',
    url(r'^full_excel_export/(?P<export_hash>[\w\-]+)$', "bihar_export_report", name="bihar_export_report"),
)