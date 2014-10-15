from django.contrib import admin
from custom.m4change.models import McctStatus


class McctStatusAdmin(admin.ModelAdmin):
    model = McctStatus
    list_display = ('form_id', 'status', 'domain', 'reason', 'received_on', 'registration_date', 'immunized',
                    'is_booking', 'is_stillbirth', 'modified_on', 'user')
    search_fields = ('form_id',)

admin.site.register(McctStatus, McctStatusAdmin)