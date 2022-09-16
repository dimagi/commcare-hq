import os
import binascii

from django.db import models


class ABDMUser(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100)
    access_token = models.CharField(max_length=2000, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.generate_token()
        return super().save(*args, **kwargs)

    def generate_token(self):
        token = binascii.hexlify(os.urandom(20)).decode()
        self.access_token = token

    @property
    def is_token_valid(self):
        # To be used in future when token expiry is introduced.
        return True

    @property
    def is_authenticated(self):
        """
        Always return True. This is a way to tell if the user has been
        authenticated in templates.
        """
        return True
