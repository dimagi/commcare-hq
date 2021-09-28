from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from django_digest.models import PartialDigest, UserNonce

from .models import HQApiKey, UserHistory


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


class CustomUserAdmin(UserAdmin):
    inlines = [
        ApiKeyInline,
    ]

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
