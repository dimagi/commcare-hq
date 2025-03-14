import uuid
from datetime import datetime
from dataclasses import asdict
from django.utils.translation import gettext as _

from dimagi.utils.chunked import chunked
from corehq.apps.users.models import WebUser
from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.apps.integration.payments.exceptions import PaymentRequestError
from corehq.apps.integration.payments.schemas import PaymentTransferDetails, PartyDetails
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.form_processor.models import CommCareCase
from corehq.apps.integration.payments.const import PaymentProperties
from corehq.apps.hqcase.utils import bulk_update_cases

CHUNK_SIZE = 100


def request_payments_for_cases(case_ids, config):
    payment_updates = []

    for payment_case in CommCareCase.objects.get_cases(case_ids=case_ids):
        payment_update = {}
        payment_submitted = False
        try:
            transaction_id = request_payment(payment_case, config)
            payment_update['transaction_id'] = transaction_id
            payment_submitted = True
        except PaymentRequestError as e:
            payment_update[PaymentProperties.PAYMENT_ERROR] = str(e)
        finally:
            payment_update[PaymentProperties.PAYMENT_SUBMITTED] = payment_submitted
            payment_update[PaymentProperties.PAYMENT_TIMESTAMP] = str(datetime.now())

        payment_updates.append(
            (payment_case.case_id, payment_update, False)
        )
        if len(payment_updates) >= CHUNK_SIZE:
            bulk_update_cases(
                config.domain, payment_updates, device_id='momo_payment_submitted'
            )
            payment_updates = []

    if payment_updates:
        bulk_update_cases(
            config.domain, payment_updates, device_id='momo_payment_submitted'
        )


def request_payment(payee_case: CommCareCase, config: MoMoConfig):
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

    transaction_id = str(uuid.uuid4())
    response = requests.post(
        '/disbursement/v2_0/deposit',
        json=request_data,
        headers={
            'X-Reference-Id': transaction_id,
            'X-Target-Environment': config.environment,
        }
    )
    if response.status_code != 202:
        raise PaymentRequestError(_("Payment request failed"))
    return transaction_id


def verify_payment_cases(domain, case_ids: list, verifying_user: WebUser):
    if not case_ids:
        return []

    payment_properties_update = {
        PaymentProperties.PAYMENT_VERIFIED: str(True),
        PaymentProperties.PAYMENT_VERIFIED_ON_UTC: str(datetime.now()),
        PaymentProperties.PAYMENT_VERIFIED_BY: verifying_user.username,
        PaymentProperties.PAYMENT_VERIFIED_BY_USER_ID: verifying_user.user_id,
    }

    updated_cases = []
    for case_ids_chunk in chunked(case_ids, CHUNK_SIZE):
        cases_updates = _get_cases_updates(case_ids_chunk, payment_properties_update)
        _, cases = handle_case_update(
            domain, cases_updates, verifying_user, 'momo_payment_verified', is_creation=False,
        )
        updated_cases.extend(cases)

    return updated_cases


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
    if _payment_already_submitted(case_data):
        raise PaymentRequestError(_("Payment has already been submitted"))


def _payment_is_verified(case_data: dict):
    return case_data.get(PaymentProperties.PAYMENT_VERIFIED, '') == 'True'


def _payment_already_submitted(case_data: dict):
    return case_data.get(PaymentProperties.PAYMENT_SUBMITTED, '') == 'True'
