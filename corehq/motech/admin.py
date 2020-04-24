from django.contrib import admin

from corehq.motech.models import ApiAuthSettings


@admin.register(ApiAuthSettings)
class ApiAuthSettingsAdmin(admin.ModelAdmin):
    model = ApiAuthSettings
    list_filter = ('auth_type',)
