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
    ]
    list_filter = ('doc_type', 'domain')


admin.site.register(AsyncIndicator, AsyncIndicatorAdmin)
