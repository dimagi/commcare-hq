from __future__ import absolute_import
from corehq.apps.users.models import CommCareUser, CouchUser
from custom.enikshay.case_utils import get_person_case_from_voucher
from custom.enikshay.exceptions import ENikshayCaseNotFound


def person_case_from_voucher_case(handler, reminder):
    voucher_case = reminder.case
    if not voucher_case:
        return None

    if voucher_case.type != 'voucher':
        return None

    try:
        return get_person_case_from_voucher(voucher_case.domain, voucher_case.case_id)
    except ENikshayCaseNotFound:
        return None


def agency_user_case_from_voucher_fulfilled_by_id(handler, reminder):
    voucher_case = reminder.case
    if not voucher_case:
        return None

    if voucher_case.type != 'voucher':
        return None

    fulfilled_by_id = voucher_case.get_case_property('voucher_fulfilled_by_id')
    if not fulfilled_by_id:
        return None

    try:
        user = CommCareUser.get_by_user_id(fulfilled_by_id, domain=voucher_case.domain)
    except CouchUser.AccountTypeError:
        user = None

    if not user:
        return None

    # get_usercase() just returns None if the user case does not exist; no exceptions raised
    return user.get_usercase()
