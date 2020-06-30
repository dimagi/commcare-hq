from django.db import models


class DialerSettings(models.Model):
    domain = models.CharField(max_length=128, unique=True)
    url = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=False)
