from django.contrib import admin
from .models import *


class TimezoneMigrationProgressAdmin(admin.ModelAdmin):

    model = TimezoneMigrationProgress
    list_display = [
        'domain',
        'migration_status',
    ]

    search_fields = [
        'domain',
        'migration_status',
    ]


admin.site.register(TimezoneMigrationProgress, TimezoneMigrationProgressAdmin)
