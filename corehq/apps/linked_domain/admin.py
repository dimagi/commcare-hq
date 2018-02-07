from __future__ import absolute_import
from django.contrib import admin
from .models import DomainLink


class DomainLinkAdmin(admin.ModelAdmin):
    model = DomainLink
    list_display = [
        'linked_domain',
        'master_domain',
        'remote_base_url',
        'last_pull',
    ]
    list_filter = [
        'linked_domain',
        'master_domain',
        'last_pull',
    ]
    search_fields = ['linked_domain', 'master_domain']


admin.site.register(DomainLink, DomainLinkAdmin)
