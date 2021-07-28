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
    readonly_fields = ['key', 'created']
    extra = 1


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


admin.site.register(HQApiKey, HQApiKeyAdmin)


class UserHistoryAdmin(admin.ModelAdmin):
    list_display = ['changed_at', 'domain', 'user_id', 'changed_by', 'action', 'message']
    list_filter = ['domain', 'action']
    sortable_by = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(UserHistory, UserHistoryAdmin)
