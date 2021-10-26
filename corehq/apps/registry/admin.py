from django.contrib import admin

from .models import DataRegistry, RegistryInvitation, RegistryGrant, RegistryPermission


class RegistryInvitationInline(admin.TabularInline):
    model = RegistryInvitation
    extra = 1


class RegistryGrantInline(admin.TabularInline):
    model = RegistryGrant
    extra = 1


class RegistryPermissionInline(admin.TabularInline):
    model = RegistryPermission
    extra = 1


@admin.register(DataRegistry)
class DataRegistryAdmin(admin.ModelAdmin):
    list_display = ['domain', 'name', 'slug', 'is_active', 'created_on']
    list_filter = ['domain', 'name', 'is_active']
    readonly_fields = ['slug']

    inlines = [
        RegistryInvitationInline,
        RegistryGrantInline,
        RegistryPermissionInline
    ]
