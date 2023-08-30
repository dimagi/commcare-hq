from django.db import models

from custom.abdm.const import STATUS_ACKNOWLEDGED, STATUS_ERROR, STATUS_TRANSFERRED, STATUS_FAILED


class HIPConsentArtefact(models.Model):
    artefact_id = models.UUIDField(unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    details = models.JSONField()
    signature = models.TextField()
    grant_acknowledgement = models.BooleanField()


class HIPHealthInformationRequest(models.Model):
    STATUS = [
        (STATUS_ACKNOWLEDGED, 'Acknowledged'),
        (STATUS_ERROR, 'Error occurred'),
        (STATUS_TRANSFERRED, 'Transferred'),
        (STATUS_FAILED, 'Failed'),
    ]

    consent_artefact = models.ForeignKey(HIPConsentArtefact, to_field='artefact_id', on_delete=models.PROTECT,
                                         related_name='health_information_request')
    transaction_id = models.UUIDField(null=True, unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    # TODO Check if  key pair is needed
    # key_pairs = models.JSONField(null=True)
    status = models.CharField(choices=STATUS, default=STATUS_ACKNOWLEDGED, max_length=40)
    error = models.JSONField(null=True)
