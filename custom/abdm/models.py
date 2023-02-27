from django.db import models

from rest_framework.authtoken.models import Token


class ABDMUser(models.Model):
    username = models.CharField(max_length=100, primary_key=True)
    access_token = models.CharField(max_length=2000, null=True, blank=True)
    domain = models.CharField(max_length=100, default="")

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.generate_token()
        return super().save(*args, **kwargs)

    def generate_token(self):
        self.access_token = Token.generate_key()

    @property
    def is_token_valid(self):
        # To be used in future when token expiry is introduced.
        return True

    @property
    def is_authenticated(self):
        """
        Always return True. This is a way to tell if the user has been
        authenticated in REST views.
        """
        return True
