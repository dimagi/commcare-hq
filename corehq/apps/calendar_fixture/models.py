from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import models


DEFAULT_DAYS_BEFORE = 300
DEFAULT_DAYS_AFTER = 90


class CalendarFixtureSettings(models.Model):
    domain = models.CharField(primary_key=True, max_length=255)
    days_before = models.PositiveIntegerField(default=DEFAULT_DAYS_BEFORE)
    days_after = models.PositiveIntegerField(default=DEFAULT_DAYS_AFTER)

    def __repr__(self):
        return '{}: {} before - {} after'.format(self.domain, self.days_before, self.days_after)

    @classmethod
    def for_domain(cls, domain):
        try:
            return cls.objects.get(domain=domain)
        except cls.DoesNotExist:
            return cls(domain=domain)
