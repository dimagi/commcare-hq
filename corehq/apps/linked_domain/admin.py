from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import DomainLink, DomainLinkHistory


class DomainLinkHistoryInline(admin.TabularInline):
    model = DomainLinkHistory


class DomainLinkAdmin(admin.ModelAdmin):
    model = DomainLink
    list_display = [
        'linked_domain',
        'master_domain',
        'remote_base_url',
        'last_pull',
        'deleted',
    ]
    list_filter = [
        'linked_domain',
        'master_domain',
        'last_pull',
    ]
    search_fields = ['linked_domain', 'master_domain']
    inlines = [
        DomainLinkHistoryInline,
    ]
    actions = [
        'delete', 'undelete'
    ]

    def delete(self, request, queryset):
        queryset.update(deleted=True)
    delete.short_description = "Mark selected items as deleted"

    def undelete(self, request, queryset):
        queryset.update(deleted=False)
    undelete.short_description = "Undelete selected items"


admin.site.disable_action('delete_selected')
admin.site.register(DomainLink, DomainLinkAdmin)
