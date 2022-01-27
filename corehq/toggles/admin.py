from django.contrib import admin

from corehq.toggles.models import ToggleAudit


@admin.register(ToggleAudit)
class ToggleAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    list_display = ('username', 'slug', 'action', 'namespace', 'item', 'randomness')
    list_filter = ('slug', 'namespace')
    ordering = ('created',)
