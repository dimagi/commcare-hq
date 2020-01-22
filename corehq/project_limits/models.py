from django.db import models


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
