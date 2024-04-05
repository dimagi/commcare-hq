from datetime import datetime, timedelta

from django.conf import settings
from django.db import models

from rest_framework.authtoken.models import Token


class ABDMUser(models.Model):
    username = models.CharField(max_length=100)
    access_token = models.CharField(max_length=2000, null=True, blank=True)
    token_created_at = models.DateTimeField(null=True)
    domain = models.CharField(max_length=100)

    class Meta:
        unique_together = ['username', 'domain']

    def generate_token(self):
        self.access_token = Token.generate_key()
        self.token_created_at = datetime.utcnow()

    def refresh_token(self):
        self.generate_token()
        self.save()

    @property
    def is_token_expired(self):
        return (self.token_created_at + timedelta(minutes=settings.ABDM_TOKEN_EXPIRY)) < datetime.utcnow()

    @property
    def is_authenticated(self):
        """
        Always return True. This is a way to tell if the user has been
        authenticated in REST views.
        """
        return True
