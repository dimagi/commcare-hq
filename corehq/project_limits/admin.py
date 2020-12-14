from django.contrib import admin

from corehq.project_limits.models import DynamicRateDefinition, RateLimitedTwoFactorLog


@admin.register(DynamicRateDefinition)
class DynamicRateDefinitionAdmin(admin.ModelAdmin):
    list_display = ('key', 'per_week', 'per_day', 'per_hour', 'per_minute', 'per_second')
    list_filter = ('key',)
    ordering = ('key',)

@admin.register(RateLimitedTwoFactorLog)
class RateLimitedTwoFactorLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'username', 'method', 'window', 'status')
    list_filter = ('username',)
    ordering = ('-date',)
