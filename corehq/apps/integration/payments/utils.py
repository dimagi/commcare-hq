from datetime import datetime

from corehq.apps.users.models import WebUser
from corehq.apps.hqcase.api.updates import handle_case_update


def verify_payment_cases(domain, case_ids: list, verifying_user: WebUser) -> tuple[int, int]:
    payment_properties_update = {
        'momo_payment_verified': str(True),
        'momo_payment_verified_on_utc': str(datetime.now()),
        'momo_payment_verified_by': verifying_user.username,
        'momo_payment_verified_by_user_id': verifying_user.user_id,
    }
    cases_updates = _get_cases_updates(case_ids, payment_properties_update)

    _, updated_cases = handle_case_update(
        domain, cases_updates, verifying_user, 'momo_payment_verified', is_creation=False,
    )
    success_count = len(updated_cases)

    return success_count, len(case_ids) - success_count


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
