from django.contrib import admin

from corehq.apps.domain.models import OperatorCallLimitSettings


class OperatorCallLimitSettingsAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'call_limit',
    ]

    search_fields = [
        'domain',
    ]


admin.site.register(OperatorCallLimitSettings, OperatorCallLimitSettingsAdmin)
