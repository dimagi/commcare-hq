from django.db import models

from custom.abdm.const import (
    STATUS_DENIED,
    STATUS_ERROR,
    STATUS_EXPIRED,
    STATUS_GRANTED,
    STATUS_PENDING,
    STATUS_REQUESTED,
    STATUS_REVOKED, STATUS_ACKNOWLEDGED, STATUS_TRANSFERRED, STATUS_FAILED,
)
from custom.abdm.models import ABDMUser


class HIUConsentRequest(models.Model):

    STATUS = (
        (STATUS_PENDING, 'Pending request from Gateway'),
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_GRANTED, 'Granted'),
        (STATUS_DENIED, 'Denied'),
        (STATUS_REVOKED, 'Revoked'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_ERROR, 'Error occurred'),
    )

    user = models.ForeignKey(ABDMUser, on_delete=models.PROTECT, related_name='consent_requests')
    gateway_request_id = models.UUIDField(null=True, unique=True)
    consent_request_id = models.UUIDField(null=True, unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    status = models.CharField(choices=STATUS, default=STATUS_PENDING, max_length=40)
    details = models.JSONField(null=True)
    error = models.JSONField(null=True)
    # Below attributes correspond to ones that are accepted by Patient when consent is granted.
    health_info_from_date = models.DateTimeField()
    health_info_to_date = models.DateTimeField()
    health_info_types = models.JSONField(default=list)
    expiry_date = models.DateTimeField()

    def update_status(self, status):
        self.status = status
        self.save()

    def update_user_amendable_details(self, consent_permission, health_info_types):
        self.health_info_from_date = consent_permission['dateRange']['from']
        self.health_info_to_date = consent_permission['dateRange']['to']
        self.expiry_date = consent_permission['dataEraseAt']
        self.health_info_types = health_info_types
        self.save()


class HIUConsentArtefact(models.Model):

    consent_request = models.ForeignKey(HIUConsentRequest, to_field='consent_request_id', on_delete=models.PROTECT,
                                        related_name='artefacts')
    gateway_request_id = models.UUIDField(null=True, unique=True)
    artefact_id = models.UUIDField(unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    details = models.JSONField(null=True)
    error = models.JSONField(null=True)


class HIUHealthInformationRequest(models.Model):
    STATUS = [
        (STATUS_PENDING, 'Pending request from Gateway'),
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_ACKNOWLEDGED, 'Acknowledged'),
        (STATUS_ERROR, 'Error occurred'),
        (STATUS_TRANSFERRED, 'Transferred'),
        (STATUS_FAILED, 'Failed'),
    ]

    consent_artefact = models.ForeignKey(HIUConsentArtefact, to_field='artefact_id', on_delete=models.PROTECT,
                                         related_name='health_information_request')
    gateway_request_id = models.UUIDField(unique=True)
    transaction_id = models.UUIDField(null=True, unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    key_material = models.JSONField(null=True)
    status = models.CharField(choices=STATUS, default=STATUS_PENDING, max_length=40)
    error = models.JSONField(null=True)

    def update_status(self, status):
        self.status = status
        self.save()
