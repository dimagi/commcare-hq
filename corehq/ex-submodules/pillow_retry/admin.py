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
        'delete_selected'
    ]
