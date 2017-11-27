from __future__ import absolute_import
from dateutil.parser import parse
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml.parser import CaseUpdateAction
from corehq.apps.locations.models import SQLLocation
from custom.enikshay.exceptions import NikshayLocationNotFound, ENikshayCaseNotFound
from custom.enikshay.case_utils import (
    get_person_case_from_episode,
    get_lab_referral_from_test,
    get_person_case_from_voucher)
from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID
from custom.enikshay.const import (
    PERSON_CASE_2B_VERSION,
    REAL_DATASET_PROPERTY_VALUE,
)
import six


def case_was_created(case):
    last_case_action = case.actions[-1]
    if last_case_action.is_case_create:
        return True


def _is_submission_from_test_location(case_id, owner_id):
    try:
        phi_location = SQLLocation.objects.get(location_id=owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for person with id: {person_id}"
            .format(location_id=owner_id, person_id=case_id)
        )
    return phi_location.metadata.get('is_test', "yes") == "yes"


def is_valid_person_submission(person_case):
    if person_case.owner_id == ARCHIVED_CASE_OWNER_ID:
        return False
    if person_case.dynamic_case_properties().get('case_version') == PERSON_CASE_2B_VERSION:
        return person_case.dynamic_case_properties().get('dataset') == REAL_DATASET_PROPERTY_VALUE
    return not _is_submission_from_test_location(person_case.case_id, person_case.owner_id)


def is_valid_episode_submission(episode_case):
    try:
        person_case = get_person_case_from_episode(episode_case.domain, episode_case)
    except ENikshayCaseNotFound:
        return False
    if person_case.dynamic_case_properties().get('case_version') == PERSON_CASE_2B_VERSION:
        return person_case.dynamic_case_properties().get('dataset') == REAL_DATASET_PROPERTY_VALUE
    return not _is_submission_from_test_location(person_case.case_id, person_case.owner_id)


def is_migrated_uatbc_episode(episode_case):
    return episode_case.get_case_property('migration_created_case') == 'true'


def is_valid_voucher_submission(voucher_case):
    try:
        person_case = get_person_case_from_voucher(voucher_case.domain, voucher_case)
    except ENikshayCaseNotFound:
        return False
    return is_valid_person_submission(person_case)


def is_valid_test_submission(test_case):
    try:
        lab_referral_case = get_lab_referral_from_test(test_case.domain, test_case.get_id)
    except ENikshayCaseNotFound:
        return False

    try:
        dmc_location = SQLLocation.objects.get(location_id=lab_referral_case.owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for lab referral with id: \
            {lab_referral_id}"
            .format(location_id=lab_referral_case.owner_id, lab_referral_id=lab_referral_case.case_id)
        )
    return dmc_location.metadata.get('is_test', "yes") == "yes"


def is_valid_archived_submission(episode_case):
    try:
        person_case = get_person_case_from_episode(episode_case.domain, episode_case)
    except ENikshayCaseNotFound:
        return False
    if person_case.dynamic_case_properties().get('case_version') == PERSON_CASE_2B_VERSION:
        return person_case.dynamic_case_properties().get('dataset') == REAL_DATASET_PROPERTY_VALUE

    owner_id = person_case.owner_id
    if owner_id == ARCHIVED_CASE_OWNER_ID:
        owner_id = person_case.dynamic_case_properties().get('last_owner', None)

    return not _is_submission_from_test_location(person_case.case_id, owner_id)


def case_properties_changed(case, case_properties):
    """NOTE: only works for SQL domains"""
    if isinstance(case_properties, six.string_types):
        case_properties = [case_properties]

    last_case_action = case.get_form_transactions()[-1]
    if last_case_action.is_case_create:
        return False

    update_actions = [
        update.get_update_action() for update in get_case_updates(last_case_action.form)
        if update.id == case.case_id
    ]
    property_changed = any(
        action for action in update_actions
        if isinstance(action, CaseUpdateAction)
        and (
            any(case_property in action.dynamic_properties for case_property in case_properties)
            or ("owner_id" in case_properties and action.owner_id)
        )
    )
    return property_changed


def string_to_date_or_None(date_string):
    if not date_string:
        return None
    try:
        return parse(date_string).date()
    except ValueError:
        return None
