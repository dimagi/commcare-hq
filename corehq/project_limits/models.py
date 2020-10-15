from django.db import models

import architect


class DynamicRateDefinition(models.Model):
    key = models.CharField(max_length=512, blank=False, null=False, unique=True, db_index=True)
    per_week = models.FloatField(default=None, blank=True, null=True)
    per_day = models.FloatField(default=None, blank=True, null=True)
    per_hour = models.FloatField(default=None, blank=True, null=True)
    per_minute = models.FloatField(default=None, blank=True, null=True)
    per_second = models.FloatField(default=None, blank=True, null=True)

    def save(self, *args, **kwargs):
        self._clear_caches()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._clear_caches()
        super().delete(*args, **kwargs)

    def _clear_caches(self):
        from corehq.project_limits.rate_limiter import get_dynamic_rate_definition
        get_dynamic_rate_definition.clear(self.key, {})


@architect.install('partition', type='range', subtype='date', constraint='week', column='date')
class RateLimitedTwoFactorLog(models.Model):
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    username = models.CharField(max_length=255, null=False, db_index=True)
    ip_address = models.CharField(max_length=45, null=False, db_index=True)
    phone_number = models.CharField(max_length=127, null=False, db_index=True)
    # 'sms', 'call' don't expect this to change
    method = models.CharField(max_length=4, null=False)
    # 'second' and 'minute' are 6 characters, 15 for headroom
    window = models.CharField(max_length=15, null=False)
    # 'number_rate_limited' is 19 characters, 31 for headroom
    status = models.CharField(max_length=31, null=False)

    def save(self, *args, **kwargs):
        kwargs['window'] = kwargs['window'] or 'unknown'
        kwargs['status'] = kwargs['status'] or 'unknown'
        super(RateLimitedTwoFactorLog, self).save(*args, **kwargs)
