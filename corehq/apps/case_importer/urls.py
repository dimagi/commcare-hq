from django.conf.urls import url
from corehq.apps.case_importer.tracking.views import case_uploads, case_upload_file, \
    update_case_upload_comment, case_upload_case_ids, case_upload_form_ids

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
    url(r'^history/uploads/(?P<upload_id>[\w-]+)/comment/$', update_case_upload_comment,
        name='case_importer_update_upload_comment'),
    url(r'^history/uploads/(?P<upload_id>[\w-]+)/$', case_upload_file,
        name='case_importer_upload_file_download'),
    url(r'^history/uploads/(?P<upload_id>[\w-]+)/form_ids.txt$', case_upload_form_ids,
        name='case_importer_upload_form_ids'),
    url(r'^history/uploads/(?P<upload_id>[\w-]+)/case_ids.txt$', case_upload_case_ids,
        name='case_importer_upload_case_ids'),
]
