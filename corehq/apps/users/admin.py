from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from django_digest.models import PartialDigest, UserNonce


class DDUserNonceAdmin(admin.ModelAdmin):
    list_display = ('user', 'nonce', 'count', 'last_used_at')


class DDPartialDigestAdmin(admin.ModelAdmin):
    list_display = ('user', 'partial_digest', 'confirmed')
    search_fields = ('login',)


admin.site.register(UserNonce, DDUserNonceAdmin)
admin.site.register(PartialDigest, DDPartialDigestAdmin)


class CustomUserAdmin(UserAdmin):
    def has_add_permission(self, request):
        return False


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
