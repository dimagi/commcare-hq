from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import AsyncIndicator


class AsyncIndicatorAdmin(admin.ModelAdmin):

    model = AsyncIndicator
    list_display = [
        'doc_id',
        'doc_type',
        'domain',
        'indicator_config_ids',
        'date_created',
        'date_queued',
        'unsuccessful_attempts'
    ]
    list_filter = ('doc_type', 'domain', 'unsuccessful_attempts')
    search_fields = ('doc_id',)


admin.site.register(AsyncIndicator, AsyncIndicatorAdmin)
