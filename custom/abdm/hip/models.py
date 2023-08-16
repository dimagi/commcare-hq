from django.db import models


class HIPConsentArtefact(models.Model):
    artefact_id = models.UUIDField(unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    details = models.JSONField()
    signature = models.TextField()
    grant_acknowledgement = models.BooleanField()
