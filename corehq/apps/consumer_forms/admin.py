from django.contrib import admin

from .models import AuthenticatedLink


@admin.register(AuthenticatedLink)
class AuthenticatedLinkAdmin(admin.ModelAdmin):
    list_display = ('link_id', 'domain', 'created_on', 'expires_on')
    list_filter = ('domain', 'created_on', 'expires_on')
