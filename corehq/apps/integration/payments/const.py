from enum import Enum
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


class PaymentStatus:
    NOT_VERIFIED = None  # None is the default value when payment cases are created and are not verified yet.
    PENDING_SUBMISSION = 'pending_submission'
    SUBMITTED = 'submitted'
    REQUEST_FAILED = 'request_failed'

    @classmethod
    def choices(cls):
        return (
            (cls.NOT_VERIFIED, _("Not Verified")),
            (cls.PENDING_SUBMISSION, _("Pending Submission")),
            (cls.SUBMITTED, _("Submitted")),
            (cls.REQUEST_FAILED, _("Request Failed")),
        )

    @classmethod
    def label_for(cls, value):
        return dict(cls.choices()).get(value, _("Invalid Status"))
