from uuid import uuid4

from django.db import models

from corehq.apps.users.util import PUBLIC_USER_ID


class PublicWebformTypes(models.TextChoices):
    # inferred based on the form and not user-defined; no need to translate
    REGISTRATION = 'registration'
    SURVEY = 'survey'


class PublicWebform(models.Model):

    domain = models.CharField()
    app_id = models.CharField()
    app_build_id = models.CharField()
    form_unique_id = models.CharField()
    endpoint_id = models.CharField()
    session_type = models.CharField(choices=PublicWebformTypes)
    allow_sms = models.BooleanField()
    allow_email = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_disabled = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['domain', 'id'])]


class PublicFormSession(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid4)
    session_key = models.UUIDField(default=uuid4, unique=True, db_index=True)
    public_webform = models.ForeignKey(PublicWebform, on_delete=models.CASCADE, db_index=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    opened_at = models.DateTimeField(null=True)
    submitted_at = models.DateTimeField(null=True)
    xform_id = models.CharField(null=True)

    class Meta:
        indexes = [models.Index(fields=['public_webform', 'id'])]
    @property
    def session_username(self):
        return f"{PUBLIC_USER_ID}{self.id.hex}@{self.public_webform.domain}.commcarehq.org"
