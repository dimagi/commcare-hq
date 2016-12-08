from django.conf.urls import url
from corehq.apps.case_importer.tracking.views import case_uploads, case_upload_file

from corehq.apps.case_importer.views import (
    excel_commit,
    excel_config,
    excel_fields,
)

urlpatterns = [
    url(r'^excel/config/$', excel_config, name='excel_config'),
    url(r'^excel/fields/$', excel_fields, name='excel_fields'),
    url(r'^excel/commit/$', excel_commit, name='excel_commit'),
    url(r'^history/uploads/$', case_uploads, name='case_importer_uploads'),
    # allow '---' as a dummy value to be able to reverse url in javascript w/o upload_id
    url(r'^history/uploads/(?P<upload_id>---|[-0-9a-f]{36})/$', case_upload_file,
        name='case_importer_upload_file_download'),
]
