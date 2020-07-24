from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from django_digest.models import PartialDigest, UserNonce

from .models import DomainPermissionsMirror, HQApiKey


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


class DomainPermissionsMirrorAdmin(admin.ModelAdmin):
    list_display = ['source', 'mirror']
    list_filter = ['source', 'mirror']


admin.site.register(DomainPermissionsMirror, DomainPermissionsMirrorAdmin)
