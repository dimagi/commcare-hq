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


CONSENT_REQUEST_STATUS_GRANTED = 'GRANTED'
CONSENT_REQUEST_STATUS_DENIED = 'DENIED'


# TODO Refine this table
class ConsentRequest(models.Model):

    CONSENT_REQUEST_STATUS = (
        ('REQUESTED', 'REQUESTED'),
        (CONSENT_REQUEST_STATUS_GRANTED, CONSENT_REQUEST_STATUS_GRANTED),
        (CONSENT_REQUEST_STATUS_DENIED, CONSENT_REQUEST_STATUS_DENIED),
        ('REVOKED', 'REVOKED'),
        ('EXPIRED', 'EXPIRED'),
        ('ERROR', 'ERROR')
    )

    request_id = models.UUIDField(unique=True)
    consent_request_id = models.UUIDField(null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    expiry_date = models.DateTimeField(null=True)
    # TODO Add support for multiple artefacts (New Table)
    artefact_id = models.UUIDField(null=True)
    patient_abha_address = models.CharField(null=True, max_length=100)
    status = models.CharField(choices=CONSENT_REQUEST_STATUS, default='REQUESTED', max_length=40)
    details = models.JSONField(null=True)


# Only for Demo
class Patient(models.Model):

    name = models.CharField(null=True, max_length=100)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    abha_address = models.CharField(null=True, max_length=100)
    health_id_number = models.CharField(null=True, max_length=100)
    address = models.JSONField(null=True)
    identifiers = models.JSONField(null=True)
