import secrets

from django.db import models


class VaultStore(models.Model):
    id = models.BigAutoField(primary_key=True)
    key = models.CharField(max_length=25, unique=True)
    value = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, blank=True, null=True)
    date_created = models.DateTimeField()

    def __init__(self, *args, **kwargs):
        super(VaultStore, self).__init__(*args, **kwargs)
        self.key = secrets.token_urlsafe(16)
