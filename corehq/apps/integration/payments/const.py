from enum import Enum
from django.db import models
from django.utils.translation import gettext as _


class PaymentProperties(str, Enum):
    PAYMENT_VERIFIED = 'payment_verified'
    PAYMENT_VERIFIED_ON_UTC = 'payment_verified_on_utc'
    PAYMENT_VERIFIED_BY = 'payment_verified_by'
    PAYMENT_VERIFIED_BY_USER_ID = 'payment_verified_by_user_id'
    PAYMENT_STATUS = 'payment_status'
    PAYMENT_TIMESTAMP = 'payment_timestamp'
    AMOUNT = 'amount'
    CURRENCY = 'currency'
    PAYEE_NOTE = 'payee_note'
    PAYER_MESSAGE = 'payer_message'
    USER_OR_CASE_ID = 'user_or_case_id'
    EMAIL = 'email'
    PHONE_NUMBER = 'phone_number'
    BATCH_NUMBER = 'batch_number'
    PAYMENT_ERROR = 'payment_error'


PAYMENT_SUCCESS_STATUS_CODE = 202
PAYMENT_SUBMITTED_DEVICE_ID = 'momo_payment_service'


class PaymentStatus(models.TextChoices):
    # For new records that have not yet been verified, the payment_status field is missing and value is None.
    # Such cases should be treated as "Not Verified" during validation or status checks. See method `from_value`.
    NOT_VERIFIED = 'not_verified', _("Not Verified")
    PENDING_SUBMISSION = 'pending_submission', _("Pending Submission")
    SUBMITTED = 'submitted', _("Submitted")
    REQUEST_FAILED = 'request_failed', _("Request failed")

    @classmethod
    def normalize(cls, value):
        value_map = {
            None: cls.NOT_VERIFIED,
            "": cls.NOT_VERIFIED,
            "not_verified": cls.NOT_VERIFIED,
            "pending_submission": cls.PENDING_SUBMISSION,
            "submitted": cls.SUBMITTED,
            "request_failed": cls.REQUEST_FAILED,
        }
        return value_map[value]

    @classmethod
    def from_value(cls, value):
        try:
            return cls.normalize(value)
        except KeyError:
            raise ValueError(f"Invalid PaymentStatus: {value}")
