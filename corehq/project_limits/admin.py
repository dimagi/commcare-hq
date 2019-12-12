from django.contrib import admin

from corehq.project_limits.models import DynamicRateDefinition


@admin.register(DynamicRateDefinition)
class DynamicRateDefinitionAdmin(admin.ModelAdmin):
    list_display = ('key', 'per_week', 'per_day', 'per_hour', 'per_minute', 'per_second')
    list_filter = ('key',)
    ordering = ('key',)
