import architect
from django.db import models
from django.conf import settings
from field_audit import audit_fields

from corehq.util.quickcache import quickcache

AVG = 'AVG'
MAX = 'MAX'

AGGREGATION_OPTIONS = [
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


class GaugeDefinition(models.Model):
    """
    An abstract model to be used to define configuration to limit gauge values.
    The model is used by GaugeLimiter class to decide weather to limit or not.
    """

    key = models.CharField(max_length=512, blank=False, null=False, unique=True, db_index=True)
    wait_for_seconds = models.IntegerField(null=False)
    acceptable_value = models.FloatField(default=None, blank=True, null=True)
    aggregator = models.CharField(max_length=10, null=True, blank=True, choices=AGGREGATION_OPTIONS)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._clear_caches()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._clear_caches()

    def _clear_caches(self):
        pass


class PillowLagGaugeDefinition(GaugeDefinition):
    max_value = models.FloatField(default=None, blank=True, null=True)
    average_value = models.FloatField(default=None, blank=True, null=True)

    def _clear_caches(self):
        from corehq.project_limits.gauge import get_pillow_throttle_definition

        get_pillow_throttle_definition.clear(self.key)


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


@audit_fields("limit")
class SystemLimit(models.Model):
    key = models.CharField(max_length=255)
    limit = models.PositiveIntegerField()
    # the domain field is reserved for extreme cases since limits should apply globally in steady state
    domain = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=['key', 'domain'], name='unique_key_per_domain_constraint')]

    def __str__(self):
        domain = f"[{self.domain}] " if self.domain else ""
        return f"{domain}{self.key}: {self.limit}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._get_global_limit.clear(self.__class__, self.key)
        self._get_domain_specific_limit.clear(self.__class__, self.key, self.domain)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._get_global_limit.clear(self.__class__, self.key)
        self._get_domain_specific_limit.clear(self.__class__, self.key, self.domain)

    @classmethod
    def for_key(cls, key, domain=''):
        """
        Return the value associated with the given key, prioritizing the domain specific entry over the general one
        """
        domain_limit = cls._get_domain_specific_limit(key, domain) if domain else None
        if domain_limit is not None:
            return domain_limit
        return cls._get_global_limit(key)

    @classmethod
    @quickcache(['key'], timeout=7 * 24 * 60 * 60, skip_arg=lambda *args, **kwargs: settings.UNIT_TESTING)
    def _get_global_limit(cls, key):
        try:
            return SystemLimit.objects.get(key=key, domain='').limit
        except SystemLimit.DoesNotExist:
            return None

    @classmethod
    @quickcache(
        ['key', 'domain'], timeout=7 * 24 * 60 * 60, skip_arg=lambda *args, **kwargs: settings.UNIT_TESTING
    )
    def _get_domain_specific_limit(cls, key, domain):
        try:
            return SystemLimit.objects.get(key=key, domain=domain).limit
        except SystemLimit.DoesNotExist:
            return None
