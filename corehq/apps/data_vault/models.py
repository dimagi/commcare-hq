import secrets

from django.db import models


def _default_key():
    return secrets.token_urlsafe(16)


class VaultStore(models.Model):
    id = models.BigAutoField(primary_key=True)
    key = models.CharField(max_length=25, default=_default_key)
    value = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, blank=True, null=True)
    date_created = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=['key'])
        ]
