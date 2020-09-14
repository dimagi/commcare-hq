import zipfile

from io import BytesIO

from django.contrib import admin
from django.http.response import HttpResponse

from .models import UserUploadRecord


class UserUploadAdmin(admin.ModelAdmin):
    list_display = ('domain', 'date_created')
    list_filter = ('domain',)
    ordering = ('-date_created',)
    search_fields =('domain',)
    actions = ['download_file']

    def download_file(self, request, queryset):
        export_file = BytesIO()
        with zipfile.ZipFile(export_file, 'w') as zip_file:
            for upload_record in queryset:
                upload_file = upload_record.get_file()
                zip_file.writestr(f'{upload_record.task_id}.csv', upload_file.read())
        export_file.seek(0)
        return HttpResponse(export_file, content_type='application/zip')

admin.site.register(UserUploadRecord, UserUploadAdmin)
