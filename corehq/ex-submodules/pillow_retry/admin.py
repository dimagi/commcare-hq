from datetime import datetime

from django.contrib import admin

from pillow_retry.models import PillowError


@admin.register(PillowError)
class PillowErrorAdmin(admin.ModelAdmin):
    model = PillowError
    list_display = [
        'pillow',
        'doc_id',
        'error_type',
        'date_created',
        'date_last_attempt',
        'date_next_attempt'
    ]
    list_filter = ('pillow', 'error_type')
    actions = [
        'delete_selected',
        'reset_attempts',
    ]

    def reset_attempts(self, request, queryset):
        queryset.update(current_attempt=0, date_next_attempt=datetime.utcnow())

    reset_attempts.short_description = "Reset Attempts"
