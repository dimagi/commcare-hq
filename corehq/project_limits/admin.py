from django.contrib import admin

from corehq.project_limits.models import (
    DynamicRateDefinition,
    PillowLagThrottleDefinition,
    RateLimitedTwoFactorLog,
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


@admin.register(PillowLagThrottleDefinition)
class PillowLagThrottleDefinitionAdmin(admin.ModelAdmin):
    list_display = ('kafka_topic', 'acceptable_delay_seconds',
                    'throttle_for_seconds', 'actionable_metric', 'enabled')
    list_filter = ('kafka_topic', 'enabled')
    ordering = ('kafka_topic',)
