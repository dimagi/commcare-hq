from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import admin

from corehq.apps.case_importer.tracking.models import CaseUploadRecord


class CaseUploadRecordAdmin(admin.ModelAdmin):
    search_fields = ['task_id__exact', 'upload_id__exact']


admin.site.register(CaseUploadRecord, CaseUploadRecordAdmin)
