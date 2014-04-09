from django.conf.urls.defaults import *

urlpatterns = patterns('custom.m4change.views',
    url(r'^update_service_status/$', 'update_service_status', name='update_service_status'),
    url(r'^full_excel_export/(?P<export_hash>[\w\-]+)$', "m4change_export_report", name="m4change_export_report"),
)
