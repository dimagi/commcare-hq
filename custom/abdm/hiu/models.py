from django.db import models

from custom.abdm.const import STATUS_PENDING, STATUS_REQUESTED, STATUS_GRANTED, STATUS_DENIED, STATUS_ERROR, \
    STATUS_REVOKED, STATUS_EXPIRED


# TODO Remove prefix 'HIU' if not required.
class HIUConsentRequest(models.Model):

    CONSENT_REQUEST_STATUS = (
        (STATUS_PENDING, 'Pending request from Gateway'),
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_GRANTED, 'Granted'),
        (STATUS_DENIED, 'Denied'),
        (STATUS_REVOKED, 'Revoked'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_ERROR, 'Error occurred'),
    )

    # unique request id for gateway api call (used to track async callbacks)
    gateway_request_id = models.UUIDField(null=True, unique=True)
    consent_request_id = models.UUIDField(null=True, unique=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    status = models.CharField(choices=CONSENT_REQUEST_STATUS, default=STATUS_PENDING, max_length=40)
    details = models.JSONField(null=True)
    error = models.JSONField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['consent_request_id'])
        ]


class HIUConsentArtefact(models.Model):
    CONSENT_ARTEFACT_STATUS = (
        (STATUS_GRANTED, 'Granted'),
        (STATUS_REVOKED, 'Revoked'),
        (STATUS_EXPIRED, 'Expired'),
    )

    consent_request = models.ForeignKey(HIUConsentRequest, to_field='consent_request_id', on_delete=models.PROTECT,
                                        related_name='artefacts')
    artefact_id = models.UUIDField(unique=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    status = models.CharField(choices=CONSENT_ARTEFACT_STATUS, max_length=40)
    details = models.JSONField(null=True)
