from django.contrib import admin

from .models import LookupTable


@admin.register(LookupTable)
class LookupTableAdmin(admin.ModelAdmin):
    list_display = ['domain', 'tag', 'is_global', 'last_modified']
    list_filter = ['is_global']
    search_fields = ['domain', 'tag']
    ordering = ['domain', 'tag']
