from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from corehq.messaging.smsbackends.telerivet.models import IncomingRequest


class IncomingRequestAdmin(admin.ModelAdmin):

    list_display = [
        'event',
        'message_id',
        'message_type',
        'from_number',
        'from_number_e164',
        'to_number',
        'time_created',
        'time_sent',
    ]

    search_fields = [
        'message_id',
        'from_number',
        'from_number_e164',
        'to_number',
        'time_created',
        'time_sent',
    ]


admin.site.register(IncomingRequest, IncomingRequestAdmin)
