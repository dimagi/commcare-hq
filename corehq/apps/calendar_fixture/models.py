from django.db import models


DEFAULT_DAYS_BEFORE = 300
DEFAULT_DAYS_AFTER = 90


class CalendarFixtureSettings(models.Model):
    domain = models.CharField(primary_key=True, max_length=255)
    days_before = models.PositiveIntegerField(default=DEFAULT_DAYS_BEFORE)
    days_after = models.PositiveIntegerField(default=DEFAULT_DAYS_AFTER)
