from __future__ import absolute_import
from django.contrib import admin
from django_digest.models import UserNonce, PartialDigest


class DDUserNonceAdmin(admin.ModelAdmin):
    list_display = ('user', 'nonce', 'count', 'last_used_at')


class DDPartialDigestAdmin(admin.ModelAdmin):
    list_display = ('user', 'partial_digest', 'confirmed')
    search_fields = ('login',)


admin.site.register(UserNonce, DDUserNonceAdmin)
admin.site.register(PartialDigest, DDPartialDigestAdmin)
