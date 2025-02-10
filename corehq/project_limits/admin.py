from django.contrib import admin

from corehq.project_limits.models import (
    DynamicRateDefinition,
    PillowLagGaugeDefinition,
    RateLimitedTwoFactorLog,
    SystemLimit,
)


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


@admin.register(PillowLagGaugeDefinition)
class PillowThrottleDefinitionAdmin(admin.ModelAdmin):
    list_display = ('key', 'wait_for_seconds',
                    'max_value', 'average_value', 'is_enabled')
    list_filter = ('key', 'is_enabled')
    ordering = ('key',)


@admin.register(SystemLimit)
class SystemLimitAdmin(admin.ModelAdmin):
    list_display = ('key', 'limit', 'domain')
    ordering = ('key',)
