from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import DomainMigrationProgress


class DomainMigrationProgressAdmin(admin.ModelAdmin):

    model = DomainMigrationProgress
    list_display = [
        'domain',
        'migration_slug',
        'migration_status',
    ]

    search_fields = [
        'domain',
        'migration_slug',
        'migration_status',
    ]


admin.site.register(DomainMigrationProgress, DomainMigrationProgressAdmin)
