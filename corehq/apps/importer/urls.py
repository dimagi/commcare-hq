from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.importer.views',
    url(r'^excel/config/$', 'excel_config', name='excel_config'),
    url(r'^excel/fields/$', 'excel_fields', name='excel_fields'),
    url(r'^excel/commit/$', 'excel_commit', name='excel_commit'),
)

