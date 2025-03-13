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

CHUNK_SIZE = 100


def request_payment(payee_case: CommCareCase, config: MoMoConfig):
    if not payee_case.case_json['momo_payment_verified'] == 'True':
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
        'momo_payment_verified': str(True),
        'momo_payment_verified_on_utc': str(datetime.now()),
        'momo_payment_verified_by': verifying_user.username,
        'momo_payment_verified_by_user_id': verifying_user.user_id,
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


def _get_transfer_details(payee_case) -> PaymentTransferDetails:
    case_json = payee_case.case_json

    if 'phone_number' in case_json:
        payee_details = PartyDetails(
            partyIdType="MSISDN",
            partyId=case_json.get('phone_number'),
        )
    elif 'email' in case_json:
        payee_details = PartyDetails(
            partyIdType="EMAIL",
            partyId=case_json.get('email'),
        )
    else:
        raise PaymentRequestError("Invalid payee details")

    return PaymentTransferDetails(
        payee=payee_details,
        amount=case_json.get('amount'),
        currency=case_json.get('currency'),
        payeeNote=case_json.get('payee_note'),
        payerMessage=case_json.get('payer_message'),
        externalId=case_json.get('user_or_case_id'),
    )
