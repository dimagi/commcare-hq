import uuid
from dataclasses import asdict
from datetime import datetime

import requests.exceptions
from django.utils.translation import gettext as _

from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_error, notify_exception

from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.apps.integration.payments.const import (
    PAYMENT_SUBMITTED_DEVICE_ID,
    PAYMENT_SUCCESS_STATUS_CODE,
    PaymentProperties,
    PaymentStatus,
    PAYMENT_STATUS_DEVICE_ID,
)
from corehq.apps.integration.payments.exceptions import PaymentRequestError
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.apps.integration.payments.schemas import (
    PartyDetails,
    PaymentTransferDetails,
)
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase

CHUNK_SIZE = 100


def request_payments_for_cases(case_ids, config):
    for case_ids_chunk in chunked(case_ids, CHUNK_SIZE):
        payment_updates = _get_payment_cases_updates(case_ids_chunk, config)
        bulk_update_cases(
            config.domain, payment_updates, device_id=PAYMENT_SUBMITTED_DEVICE_ID
        )


def _get_payment_cases_updates(case_ids_chunk, config):
    payment_updates = []
    for payment_case in CommCareCase.objects.get_cases(case_ids=list(case_ids_chunk)):
        print("Processing payment case:", payment_case.case_id)
        # Additional safeguard to ensure we only process cases that are pending submission
        payment_status_value = payment_case.get_case_property(PaymentProperties.PAYMENT_STATUS)
        if PaymentStatus.from_value(payment_status_value) != PaymentStatus.PENDING_SUBMISSION:
            continue

        payment_update = request_payment(payment_case, config)

        should_close = False
        payment_updates.append(
            (payment_case.case_id, payment_update, should_close)
        )
    return payment_updates


def request_payment(payment_case: CommCareCase, config: MoMoConfig):
    payment_update = {
        PaymentProperties.PAYMENT_TIMESTAMP: datetime.utcnow().isoformat(),
        PaymentProperties.PAYMENT_ERROR: '',
    }

    try:
        transaction_id = _request_payment(payment_case, config)
        payment_update.update({
            'transaction_id': transaction_id,  # can be used to check payment status
            PaymentProperties.PAYMENT_STATUS: PaymentStatus.SUBMITTED,
        })
    except PaymentRequestError as e:
        payment_update.update({
            PaymentProperties.PAYMENT_ERROR: str(e),
            PaymentProperties.PAYMENT_STATUS: PaymentStatus.REQUEST_FAILED,
        })
    except Exception as e:
        print("Unexpected error during payment request for case %s and %s", payment_case.case_id, str(e))
        # We need to know when anything goes wrong
        payment_update.update({
            PaymentProperties.PAYMENT_ERROR: _("Something went wrong"),
            PaymentProperties.PAYMENT_STATUS: PaymentStatus.REQUEST_FAILED,
        })

    return payment_update


def _request_payment(payee_case: CommCareCase, config: MoMoConfig):
    _validate_payment_request(payee_case.case_json)
    transfer_details = _get_transfer_details(payee_case)
    transaction_id = _make_payment_request(
        request_data=asdict(transfer_details),
        config=config,
    )
    return transaction_id


def _make_payment_request(request_data, config: MoMoConfig):
    connection_settings = config.connection_settings
    requests = connection_settings.get_requests()
    print("Performing payment request for:", request_data)

    transaction_id = str(uuid.uuid4())
    response = requests.post(
        '/disbursement/v2_0/deposit',
        json=request_data,
        headers={
            'X-Reference-Id': transaction_id,
            'X-Target-Environment': config.environment,
        }
    )
    print("Create Status Code:", response.status_code)
    if response.status_code != PAYMENT_SUCCESS_STATUS_CODE:
        raise PaymentRequestError(_("Payment request failed"))
    return transaction_id


def verify_payment_cases(domain, case_ids: list, verifying_user: WebUser):
    if not case_ids:
        return []

    valid_statuses_for_verification = [PaymentStatus.NOT_VERIFIED, PaymentStatus.REQUEST_FAILED]
    if _any_invalid_payment_status(case_ids, domain, valid_statuses_for_verification):
        raise PaymentRequestError(
            _("Only payments in '{}' or '{}' state are eligible for verification.".format(
                PaymentStatus.NOT_VERIFIED.label, PaymentStatus.REQUEST_FAILED.label
            ))
        )
    payment_properties_update = {
        PaymentProperties.PAYMENT_VERIFIED: 'True',
        PaymentProperties.PAYMENT_VERIFIED_ON_UTC: str(datetime.now()),
        PaymentProperties.PAYMENT_VERIFIED_BY: verifying_user.username,
        PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID: verifying_user.user_id,
        PaymentProperties.PAYMENT_STATUS: PaymentStatus.PENDING_SUBMISSION,
    }

    updated_cases = []
    for case_ids_chunk in chunked(case_ids, CHUNK_SIZE):
        cases_updates = _get_cases_updates(case_ids_chunk, payment_properties_update)
        xform, cases = handle_case_update(
            domain, cases_updates, verifying_user, 'momo_payment_verified', is_creation=False,
        )
        updated_cases.extend(cases)

    return updated_cases


def _any_invalid_payment_status(case_ids, domain, valid_statuses):
    for case in CommCareCase.objects.iter_cases(case_ids, domain):
        payment_status_value = case.get_case_property(PaymentProperties.PAYMENT_STATUS)
        if PaymentStatus.from_value(payment_status_value) not in valid_statuses:
            return True
    return False


def _get_cases_updates(case_ids, updates):
    cases = []
    for case_id in case_ids:
        case = {
            'case_id': case_id,
            'properties': updates,
            'create': False,
        }
        cases.append(case)
    return cases


def _get_transfer_details(payee_case: CommCareCase) -> PaymentTransferDetails:
    case_json = payee_case.case_json

    return PaymentTransferDetails(
        payee=_get_payee_details(case_json),
        amount=case_json.get(PaymentProperties.AMOUNT),
        currency=case_json.get(PaymentProperties.CURRENCY),
        payeeNote=case_json.get(PaymentProperties.PAYEE_NOTE),
        payerMessage=case_json.get(PaymentProperties.PAYER_MESSAGE),
        externalId=case_json.get(PaymentProperties.USER_OR_CASE_ID),
    )


def _get_payee_details(case_data: dict) -> PartyDetails:
    if case_data.get(PaymentProperties.PHONE_NUMBER):
        return PartyDetails(
            partyIdType="MSISDN",
            partyId=case_data.get(PaymentProperties.PHONE_NUMBER),
        )
    elif case_data.get(PaymentProperties.EMAIL):
        return PartyDetails(
            partyIdType="EMAIL",
            partyId=case_data.get(PaymentProperties.EMAIL),
        )
    else:
        raise PaymentRequestError(_("Invalid payee details"))


def _validate_payment_request(case_data: dict):
    if not _payment_is_verified(case_data):
        raise PaymentRequestError(_("Payment has not been verified"))
    if _payment_already_requested(case_data):
        raise PaymentRequestError(_("Payment has already been requested"))


def _payment_is_verified(case_data: dict):
    return case_data.get(PaymentProperties.PAYMENT_VERIFIED) == 'True'


def _payment_already_requested(case_data: dict):
    status = case_data.get(PaymentProperties.PAYMENT_STATUS)
    return PaymentStatus.from_value(status) == PaymentStatus.SUBMITTED


def revert_payment_verification(domain, case_ids: list):
    if not case_ids:
        return []

    if _any_invalid_payment_status(case_ids, domain, [PaymentStatus.PENDING_SUBMISSION]):
        raise PaymentRequestError(
            _("Only payments in the '{}' state are eligible for verification reversal.".format(
                PaymentStatus.PENDING_SUBMISSION.label
            ))
        )

    return _update_payment_properties_for_revert(domain, case_ids)


def _update_payment_properties_for_revert(domain, case_ids: list):
    updated_cases = []
    payment_properties_update = _properties_to_update_for_revert()
    for case_ids_chunk in chunked(case_ids, CHUNK_SIZE):
        case_changes = [(case_id, payment_properties_update, False) for case_id in case_ids_chunk]
        xform, cases = bulk_update_cases(
            domain, case_changes, 'momo_payment_verification_reverted'
        )
        updated_cases.extend(cases)

    return updated_cases


def _properties_to_update_for_revert():
    return {
        PaymentProperties.PAYMENT_VERIFIED: 'False',
        PaymentProperties.PAYMENT_VERIFIED_ON_UTC: '',
        PaymentProperties.PAYMENT_VERIFIED_BY: '',
        PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID: '',
        PaymentProperties.PAYMENT_STATUS: PaymentStatus.NOT_VERIFIED,
    }


def request_payments_status_for_cases(case_ids, config):
    for case_ids_chunk in chunked(case_ids, CHUNK_SIZE):
        status_updates = []
        for payment_case in CommCareCase.objects.get_cases(case_ids=list(case_ids_chunk)):
            payment_status_value = payment_case.get_case_property(PaymentProperties.PAYMENT_STATUS)
            if PaymentStatus.from_value(payment_status_value) != PaymentStatus.SUBMITTED:
                continue
            try:
                status_update = request_payment_status(payment_case, config)
            except PaymentRequestError:
                # Will retry in next run
                continue
            status_updates.append(
                (payment_case.case_id, status_update, False)
            )
        bulk_update_cases(
            config.domain, status_updates, device_id=PAYMENT_STATUS_DEVICE_ID
        )


def request_payment_status(payment_case: CommCareCase, config: MoMoConfig):
    # TODO Consider a user friendly description for possible failure reasons instead of using API 
    # response directly.
    transaction_id = payment_case.get_case_property('transaction_id')
    if not transaction_id:
        raise PaymentRequestError(_("No transaction ID found for payment case."))

    status_update = {}
    try:
        print(f"Fetching payment status for payment_case {payment_case.case_id} and transaction id {transaction_id}")
        response = _make_payment_status_request(transaction_id, config)
        response_data = response.json()
        status = response_data.get('status', '').lower()
        failure_reason = response_data.get('reason')
    except requests.exceptions.HTTPError as err:
        code = err.response.status_code
        print("HTTP error {}".format(code))
        if code == 404:
            status = PaymentStatus.ERROR
            failure_reason = _("Payment transaction not found")
        elif code == 500:
            status = PaymentStatus.ERROR
            failure_reason = err.response.json().get('code', _("500 error received from API"))
        elif code in (502, 503, 504):
            # Retry on server errors
            raise PaymentRequestError(_("Failed to fetch payment status"))
        else:
            # Unexpected HTTP errors
            status = PaymentStatus.ERROR
            failure_reason = _("Unexpected HTTP error occurred with status: {}".format(code))
            details = {
                'domain': config.domain,
                'transaction_id': transaction_id,
                'error': str(err.response.text),
            }
            notify_error(f"[MoMo Payments] Unexpected HTTP error {code} while fetching status.", details=details)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        raise PaymentRequestError(_("Failed to fetch payment status"))
    except Exception as e:
        details = {
            'domain': config.domain,
            'transaction_id': transaction_id,
            'error': str(e),
        }
        notify_exception(None, "[MoMo Payments] Unexpected error occurred while fetching status", details=details)
        status = PaymentStatus.ERROR
        failure_reason = _("Unexpected HTTP error occurred")

    if status in ('successful', 'failed', PaymentStatus.ERROR):
        status_update[PaymentProperties.PAYMENT_STATUS] = status
    else:  # Just a future proofing measure in case API returns an unexpected status value
        status_update[PaymentProperties.PAYMENT_STATUS] = PaymentStatus.ERROR
        failure_reason = _("Unexpected status value from API: {} with reason: {}".format(status, failure_reason))
    if failure_reason:
        status_update.update({
            PaymentProperties.PAYMENT_ERROR: failure_reason,
        })
    print("Status update for case {}: {}".format(payment_case.case_id, status_update))
    return status_update


def _make_payment_status_request(reference_id, config: MoMoConfig):
    connection_settings = config.connection_settings
    requests = connection_settings.get_requests()
    response = requests.get(
        f'/disbursement/v1_0/deposit/{reference_id}',
        headers={
            'X-Target-Environment': config.environment,
        }
    )
    response.raise_for_status()
    return response
