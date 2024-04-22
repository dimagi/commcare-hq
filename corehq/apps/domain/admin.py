from django.contrib import admin

from corehq.apps.domain.models import DomainSettings, OperatorCallLimitSettings


class DomainSettingsAdmin(admin.ModelAdmin):
    list_display = ('domain',)
    search_fields = ('domain',)


class OperatorCallLimitSettingsAdmin(admin.ModelAdmin):
    list_display = ('domain', 'call_limit')
    search_fields = ('domain',)


admin.site.register(DomainSettings, DomainSettingsAdmin)
admin.site.register(OperatorCallLimitSettings, OperatorCallLimitSettingsAdmin)
