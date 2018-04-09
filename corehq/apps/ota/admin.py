from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import DemoUserRestore


class DemoUserRestoreAdmin(admin.ModelAdmin):
    model = DemoUserRestore
    list_display = ['id', 'demo_user_id', 'timestamp_created', 'restore_blob_id']
    list_filter = ['demo_user_id']


admin.site.register(DemoUserRestore, DemoUserRestoreAdmin)
