from __future__ import absolute_import
from django.contrib import admin

from .models import ZapierSubscription


class ZapierSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('domain', 'user_id', 'repeater_id', 'event_name', 'url')
    list_filter = ('domain', 'event_name')


admin.site.register(ZapierSubscription, ZapierSubscriptionAdmin)
