from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from django_digest.models import PartialDigest, UserNonce

from .models import HQApiKey, UserHistory
from .user_data import SQLUserData


class DDUserNonceAdmin(admin.ModelAdmin):
    list_display = ('user', 'nonce', 'count', 'last_used_at')


class DDPartialDigestAdmin(admin.ModelAdmin):
    list_display = ('user', 'partial_digest', 'confirmed')
    search_fields = ('login',)


admin.site.register(UserNonce, DDUserNonceAdmin)
admin.site.register(PartialDigest, DDPartialDigestAdmin)


class ApiKeyInline(admin.TabularInline):
    model = HQApiKey
    readonly_fields = ('created',)
    exclude = ('key',)
    extra = 0

    def has_add_permission(self, request, obj):
        return False


def _copy_fieldsets(fieldsets, excluding_fields=()):
    """
    Return a deep copy of ModelAdmin `fieldsets` property, removing certain fields

    :param: fieldsets - fieldsets property to copy
    :param: excluding_fields - fields to remove

    """
    # fieldsets is structured like ((display_name, {'fields': fields}), ...)
    return tuple(
        # deep copy based on its known structure...
        (display_name, dict(fields_dict, fields=tuple(
            field for field in fields_dict["fields"]
            # ...removing excluded fields
            if field not in excluding_fields
        )))
        for display_name, fields_dict in fieldsets
    )


class CustomUserAdmin(UserAdmin):
    inlines = [
        ApiKeyInline,
    ]

    fieldsets = _copy_fieldsets(UserAdmin.fieldsets, excluding_fields=("is_superuser", "is_staff"))

    def has_add_permission(self, request):
        return False


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


class HQApiKeyAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'created', 'domain']
    list_filter = ['created', 'domain']

    readonly_fields = ('created',)
    exclude = ('key',)


admin.site.register(HQApiKey, HQApiKeyAdmin)


class UserHistoryAdmin(admin.ModelAdmin):
    list_display = ['changed_at', 'by_domain', 'for_domain', 'user_type', 'user_id', 'changed_by', 'action',
                    'changes', 'change_messages', 'changed_via', 'user_upload_record_id']
    list_filter = ['by_domain', 'for_domain']
    sortable_by = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(UserHistory, UserHistoryAdmin)


class UserDataAdmin(admin.ModelAdmin):
    list_display = ['django_user', 'domain', 'profile', 'modified_on']
    search_fields = ('django_user', 'domain')


admin.site.register(SQLUserData, UserDataAdmin)
