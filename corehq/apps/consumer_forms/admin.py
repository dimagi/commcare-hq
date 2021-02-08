from django.contrib import admin

from .models import AuthenticatedLink, CaseReference


@admin.register(AuthenticatedLink)
class AuthenticatedLinkAdmin(admin.ModelAdmin):
    list_display = ('link_id', 'domain', 'created_on', 'expires_on')
    list_filter = ('domain', 'created_on', 'expires_on')


@admin.register(CaseReference)
class CaseReferenceAdmin(admin.ModelAdmin):
    list_display = ('case_id', 'link')
