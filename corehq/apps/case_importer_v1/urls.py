from django.conf.urls import url

from corehq.apps.case_importer_v1.views import (
    excel_commit,
    excel_config,
    excel_fields,
    importer_job_poll,
)

urlpatterns = [
    url(r'^excel/config/$', excel_config, name='excel_config'),
    url(r'^excel/fields/$', excel_fields, name='excel_fields'),
    url(r'^excel/commit/$', excel_commit, name='excel_commit'),
    url(r'^importer_ajax/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        importer_job_poll, name='importer_job_poll'),
]
