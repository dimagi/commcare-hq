from tastypie.models import ApiKey
from tastypie.admin import ApiKeyInline, ApiKeyAdmin

from django.contrib import admin

from corehq.apps.hqwebapp.models import ApiKeySettings


class ApiKeySettingsInline(admin.TabularInline):
    model = ApiKeySettings


class ApiKeyAdmin(ApiKeyAdmin):
    inlines = [ApiKeySettingsInline]
    list_display = ApiKeyAdmin.list_display + ['ip_whitelist']

    def ip_whitelist(self, obj):
        return obj.apikeysettings.ip_whitelist

admin.site.unregister(ApiKey)
admin.site.register(ApiKey, ApiKeyAdmin)
