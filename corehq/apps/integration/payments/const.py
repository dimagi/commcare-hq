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
    CAMPAIGN = 'campaign'
    ACTIVITY = 'activity'
    FUNDER = 'funder'
    PAYMENT_ERROR = 'payment_error'
    PAYMENT_ERROR_MESSAGE = 'payment_error_message'
    # Tracks how many times we attempted to fetch payment status (including first attempt).
    # Only stored for pending or request error
    PAYMENT_STATUS_ATTEMPT_COUNT = 'payment_status_attempt_count'


PAYMENT_SUCCESS_STATUS_CODE = 202
PAYMENT_SUBMITTED_DEVICE_ID = 'momo_payment_service'
PAYMENT_STATUS_DEVICE_ID = 'momo_payment_status_service'
PAYMENT_STATUS_RETRY_MAX_ATTEMPTS = 4


class PaymentStatus(models.TextChoices):
    # For new records that have not yet been verified, the payment_status field is missing and value is None.
    # Such cases should be treated as "Not Verified" during validation or status checks. See method `from_value`.
    NOT_VERIFIED = 'not_verified', _("Not Verified")
    PENDING_SUBMISSION = 'pending_submission', _("Pending Submission")
    SUBMITTED = 'submitted', _("Submitted")
    REQUEST_FAILED = 'request_failed', _("Request failed")
    SUCCESSFUL = 'successful', _("Successful")
    FAILED = 'failed', _("Failed")
    PENDING_PROVIDER = 'pending', _("Pending with Provider")
    ERROR = 'error', _("Error")

    @classmethod
    def normalize(cls, value):
        value_map = {
            None: cls.NOT_VERIFIED,
            "": cls.NOT_VERIFIED,
            "not_verified": cls.NOT_VERIFIED,
            "pending_submission": cls.PENDING_SUBMISSION,
            "submitted": cls.SUBMITTED,
            "request_failed": cls.REQUEST_FAILED,
            "successful": cls.SUCCESSFUL,
            "failed": cls.FAILED,
            "pending": cls.PENDING_PROVIDER,
            "error": cls.ERROR,
        }
        return value_map[value]

    @classmethod
    def from_value(cls, value):
        try:
            return cls.normalize(value)
        except KeyError:
            raise ValueError(f"Invalid PaymentStatus: {value}")


# Error codes from https://momodeveloper.mtn.com/api-documentation/testing
# and https://momodeveloper.mtn.com/API-collections#api=disbursement&operation=GetDepositStatus
class PaymentStatusErrorCode(models.TextChoices):
    # MoMo API Error Codes
    DEPOSIT_PAYER_FAILED = 'DepositPayerFailed', _("The deposit transaction failed.")
    DEPOSIT_PAYER_REJECTED = 'DepositPayerRejected', _("The deposit transaction was rejected by the payer.")
    DEPOSIT_PAYER_EXPIRED = 'DepositPayerExpired', _("The deposit transaction request expired before completion.")
    DEPOSIT_PAYER_ONGOING = 'DepositPayerOngoing', _("The deposit transaction is still in progress.")
    DEPOSIT_PAYER_DELAYED = 'DepositPayerDelayed', _("The deposit transaction has been delayed.")
    DEPOSIT_PAYER_NOT_FOUND = 'DepositPayerNotFound', _("The deposit transaction was not found.")
    DEPOSIT_PAYER_PAYEE_NOT_ALLOWED_TO_RECEIVE = (
        "DepositPayerPayeeNotAllowedToReceive",
        _("The payee is not allowed to receive the deposit transaction.")
    )
    DEPOSIT_PAYER_NOT_ALLOWED = (
        "DepositPayerNotAllowed",
        _("The payer is not allowed to perform this deposit transaction.")
    )
    DEPOSIT_PAYER_NOT_ALLOWED_TARGET_ENVIRONMENT = (
        "DepositPayerNotAllowedTargetEnvironment",
        _("The deposit transaction is not allowed in the target environment.")
    )
    DEPOSIT_PAYER_INVALID_CALLBACK_URL_HOST = (
        "DepositPayerInvalidCallbackUrlHost",
        _("The callback URL host provided for the deposit transaction is invalid.")
    )
    DEPOSIT_PAYER_INVALID_CURRENCY = (
        "DepositPayerInvalidCurrency",
        _("The currency specified for the deposit transaction is invalid.")
    )
    DEPOSIT_PAYER_INTERNAL_PROCESSING_ERROR = (
        "DepositPayerInternalProcessingError",
        _("An internal processing error occurred during the deposit transaction.")
    )
    DEPOSIT_PAYER_SERVICE_UNAVAILABLE = (
        "DepositPayerServiceUnavailable",
        _("The deposit transaction service is currently unavailable.")
    )
    DEPOSIT_PAYER_COULD_NOT_PERFORM_TRANSACTION = (
        "DepositPayerCouldNotPerformTransaction",
        _("The deposit transaction could not be performed.")
    )

    # General API Error Codes
    PAYEE_NOT_FOUND = 'PAYEE_NOT_FOUND', _("The specified payee account could not be found.")
    PAYER_NOT_FOUND = 'PAYER_NOT_FOUND', _("The specified payer account could not be found.")
    # Note: Based on sandbox documentation, this is same as DepositPayerNotAllowed
    NOT_ALLOWED = 'NOT_ALLOWED', _("The payer is not allowed to perform this deposit transaction.")
    NOT_ALLOWED_TARGET_ENVIRONMENT = 'NOT_ALLOWED_TARGET_ENVIRONMENT', _("The target environment is not allowed.")
    INVALID_CALLBACK_URL_HOST = 'INVALID_CALLBACK_URL_HOST', _("The callback URL host is invalid.")
    INVALID_CURRENCY = 'INVALID_CURRENCY', _("The specified currency is invalid.")
    SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE', _("The service is temporarily unavailable.")
    INTERNAL_PROCESSING_ERROR = 'INTERNAL_PROCESSING_ERROR', _("An internal processing error occurred.")
    NOT_ENOUGH_FUNDS = 'NOT_ENOUGH_FUNDS', _("The payer account does not have enough funds.")
    PAYER_LIMIT_REACHED = 'PAYER_LIMIT_REACHED', _("The payer has reached their transaction limit.")
    PAYEE_NOT_ALLOWED_TO_RECEIVE = 'PAYEE_NOT_ALLOWED_TO_RECEIVE', _("The payee is not allowed to receive funds.")
    PAYMENT_NOT_APPROVED = 'PAYMENT_NOT_APPROVED', _("The payment was not approved by the payer.")
    RESOURCE_NOT_FOUND = 'RESOURCE_NOT_FOUND', _("The requested resource was not found.")
    APPROVAL_REJECTED = 'APPROVAL_REJECTED', _("The transaction approval was rejected.")
    EXPIRED = 'EXPIRED', _("The transaction has expired.")
    TRANSACTION_CANCELED = 'TRANSACTION_CANCELED', _("The transaction was canceled.")
    RESOURCE_ALREADY_EXIST = 'RESOURCE_ALREADY_EXIST', _("The resource already exists.")

    # Custom Error Codes for internal use
    MISSING_TRANSACTION_ID = 'MissingTransactionId', _("Transaction ID is missing in the record")
    HTTP_ERROR_404 = 'HttpError404', _("Payment transaction not found")
    UNEXPECTED_ERROR = 'UnexpectedError', _("Unexpected error occurred")
    PAYMENT_REQUEST_ERROR = (
        'PaymentRequestError',
        _("Error occurred during payment request. Reach out to support if the issue persists.")
    )
    MaxRetryExceededRequestError = _("Maximum retry attempts exceeded with request error.")
    MaxRetryExceededPendingStatus = _("Maximum retry attempts exceeded with pending status")
