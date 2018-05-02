from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import PillowError


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


admin.site.register(PillowError, PillowErrorAdmin)
