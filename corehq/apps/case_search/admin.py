from django.contrib import admin

from .models import CaseSearchConfig


@admin.register(CaseSearchConfig)
class CaseSearchConfigAdmin(admin.ModelAdmin):
    list_display = ['domain', 'enabled']
    list_filter = ['domain', 'enabled']
    search_fields = ['domain']
    exclude = ['fuzzy_properties', 'ignore_patterns']
