from django.db import models

from custom.abdm.const import STATUS_ACKNOWLEDGED, STATUS_ERROR, STATUS_TRANSFERRED, STATUS_FAILED, STATUS_PENDING, \
    STATUS_SUCCESS
from custom.abdm.models import ABDMUser


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
    status = models.CharField(choices=STATUS, default=STATUS_ACKNOWLEDGED, max_length=40)
    error = models.JSONField(null=True)

    def update_status(self, status):
        self.status = status
        self.save()


class HIPLinkRequest(models.Model):

    STATUS = [
        (STATUS_PENDING, 'Pending request from Gateway'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_ERROR, 'Error')
    ]

    user = models.ForeignKey(ABDMUser, on_delete=models.PROTECT, related_name='link_requests')
    patient_reference = models.CharField(max_length=255)
    hip_id = models.CharField(max_length=255)
    gateway_request_id = models.UUIDField(unique=True)
    status = models.CharField(choices=STATUS, default=STATUS_PENDING, max_length=40)
    error = models.JSONField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    # TODO Add index for patient_reference and hip id combo


class HIPCareContext(models.Model):
    care_context_number = models.CharField(max_length=255)
    link_request = models.ForeignKey(HIPLinkRequest, on_delete=models.PROTECT,
                                     related_name='care_contexts')
