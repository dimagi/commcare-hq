from __future__ import absolute_import
from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.util.quickcache import quickcache
from custom.enikshay.case_utils import get_person_case_from_voucher
from custom.enikshay.const import LOCATION_SITE_CODE_MEHSANA
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


@quickcache(['location.location_id'], timeout=4 * 60 * 60)
def located_in_mehsana(location):
    return location.get_ancestors().filter(site_code=LOCATION_SITE_CODE_MEHSANA).count() > 0


def get_user_cases_at_location(location):
    users = get_all_users_by_location(location.domain, location.location_id)
    user_cases = [u.memoized_usercase for u in users if isinstance(u, CommCareUser) and u.is_active]
    return [case for case in user_cases if case]


def beneficiary_registration_recipients(handler, reminder):
    beneficiary = reminder.case

    try:
        owner_location = SQLLocation.active_objects.get(domain=reminder.domain, location_id=beneficiary.owner_id)
    except SQLLocation.DoesNotExist:
        return beneficiary

    if not located_in_mehsana(owner_location):
        return beneficiary

    fo_location_id = beneficiary.get_case_property('fo')
    if not fo_location_id:
        return beneficiary

    try:
        fo_location = SQLLocation.active_objects.get(domain=reminder.domain, location_id=fo_location_id)
    except SQLLocation.DoesNotExist:
        return beneficiary

    additional_recipients = get_user_cases_at_location(fo_location)
    if not additional_recipients:
        return beneficiary

    return [beneficiary] + additional_recipients


def prescription_voucher_alert_recipients(handler, reminder):
    beneficiary = person_case_from_voucher_case(handler, reminder)
    if beneficiary is None:
        return None

    try:
        owner_location = SQLLocation.active_objects.get(domain=reminder.domain, location_id=beneficiary.owner_id)
    except SQLLocation.DoesNotExist:
        return beneficiary

    if not located_in_mehsana(owner_location):
        return beneficiary

    additional_recipients = get_user_cases_at_location(owner_location)
    if not additional_recipients:
        return beneficiary

    return [beneficiary] + additional_recipients
