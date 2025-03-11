from datetime import datetime

from dimagi.utils.chunked import chunked
from corehq.apps.users.models import WebUser
from corehq.apps.hqcase.api.updates import handle_case_update

CHUNK_SIZE = 100


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
