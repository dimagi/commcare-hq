from django.db import models


class DynamicRateDefinition(models.Model):
    key = models.CharField(max_length=512, blank=False, null=False, unique=True, db_index=True)
    per_week = models.FloatField(default=None, blank=True, null=True)
    per_day = models.FloatField(default=None, blank=True, null=True)
    per_hour = models.FloatField(default=None, blank=True, null=True)
    per_minute = models.FloatField(default=None, blank=True, null=True)
    per_second = models.FloatField(default=None, blank=True, null=True)
