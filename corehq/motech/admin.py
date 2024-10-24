from django.contrib import admin
from django.utils.html import escape
from .models import ConnectionSettings


class ConnectionSettingsAdmin(admin.ModelAdmin):
    model = ConnectionSettings
    fieldsets = [(None, {
        'description': escape('To edit, go to /a/<domain>/motech/conn/'),
        'fields': [
            'domain',
            'name',
            'notify_addresses_str',
            'url',
            'auth_type',
            'skip_cert_verify',
            'is_deleted',
        ],
    })]
    search_fields = ('name', 'domain',)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(ConnectionSettings, ConnectionSettingsAdmin)
