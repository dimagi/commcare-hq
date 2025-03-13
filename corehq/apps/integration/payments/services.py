import uuid
from datetime import datetime
from dataclasses import asdict

from dimagi.utils.chunked import chunked
from corehq.apps.users.models import WebUser
from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.apps.integration.payments.exceptions import PaymentRequestError
from corehq.apps.integration.payments.schemas import PaymentTransferDetails, PartyDetails
from corehq.apps.integration.payments.models import MoMoConfig
from corehq.form_processor.models import CommCareCase
from corehq.apps.integration.payments.const import PaymentProperties

CHUNK_SIZE = 100


def request_payment(payee_case: CommCareCase, config: MoMoConfig):
    if not _payment_is_verified(payee_case):
        raise PaymentRequestError("Payment has not been verified")

    connection_settings = config.connection_settings
    requests = connection_settings.get_requests()

    transfer_details = _get_transfer_details(payee_case)
    transaction_id = str(uuid.uuid4())

    response = requests.post(
        '/disbursement/v2_0/deposit',
        json=asdict(transfer_details),
        headers={
            'X-Reference-Id': transaction_id,
            'X-Target-Environment': config.environment,
        }
    )
    if response.status_code != 202:
        raise PaymentRequestError("Payment request failed")
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
    if PaymentProperties.PHONE_NUMBER in case_data:
        return PartyDetails(
            partyIdType="MSISDN",
            partyId=case_data.get(PaymentProperties.PHONE_NUMBER),
        )
    elif PaymentProperties.EMAIL in case_data:
        return PartyDetails(
            partyIdType="EMAIL",
            partyId=case_data.get(PaymentProperties.EMAIL),
        )
    else:
        raise PaymentRequestError("Invalid payee details")


def _payment_is_verified(payee_case: CommCareCase):
    return payee_case.case_json[PaymentProperties.PAYMENT_VERIFIED] == 'True'
