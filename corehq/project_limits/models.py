from django.db import models

import architect

AVG = 'AVG'
MAX = 'MAX'

ACTIONABLE_METRIC_CHOICES = [
    (AVG, 'Average'),
    (MAX, 'Maximum'),
]


class DynamicRateDefinition(models.Model):
    key = models.CharField(max_length=512, blank=False, null=False, unique=True, db_index=True)
    per_week = models.FloatField(default=None, blank=True, null=True)
    per_day = models.FloatField(default=None, blank=True, null=True)
    per_hour = models.FloatField(default=None, blank=True, null=True)
    per_minute = models.FloatField(default=None, blank=True, null=True)
    per_second = models.FloatField(default=None, blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._clear_caches()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._clear_caches()

    def _clear_caches(self):
        from corehq.project_limits.rate_limiter import get_dynamic_rate_definition
        get_dynamic_rate_definition.clear(self.key, {})


class PillowLagThrottleDefinition(models.Model):

    kafka_topic = models.CharField(max_length=255, blank=False, null=False, unique=True, db_index=True)
    acceptable_delay_seconds = models.IntegerField(null=False)
    throttle_for_seconds = models.IntegerField(null=False)
    actionable_metric = models.CharField(max_length=10, null=False, choices=ACTIONABLE_METRIC_CHOICES)
    enabled = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._clear_caches()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._clear_caches()

    def _clear_caches(self):
        from corehq.project_limits.rate_limiter import get_pillow_throttle_definition
        get_pillow_throttle_definition.clear(self.kafka_topic, {})


@architect.install('partition', type='range', subtype='date', constraint='week', column='date')
class RateLimitedTwoFactorLog(models.Model):
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    username = models.CharField(max_length=255, null=False, db_index=True)
    ip_address = models.CharField(max_length=45, null=False, db_index=True)
    phone_number = models.CharField(max_length=127, null=False, db_index=True)
    # 'sms', 'call' don't expect this to change
    method = models.CharField(max_length=4, null=False)
    # largest input is 'unknown', 15 for headroom
    window = models.CharField(max_length=15, null=False)
    # largest input is 'number_rate_limited', 31 for headroom
    status = models.CharField(max_length=31, null=False)
