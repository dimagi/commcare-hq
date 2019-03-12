from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import admin

from corehq.apps.case_importer.tracking.models import CaseUploadRecord


class CaseUploadRecordAdmin(admin.ModelAdmin):
    list_display = ['domain', 'task_id', 'upload_id']
    search_fields = ['task_id__exact', 'upload_id__exact']
    readonly_fields = ['upload_file_meta']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(CaseUploadRecord, CaseUploadRecordAdmin)
