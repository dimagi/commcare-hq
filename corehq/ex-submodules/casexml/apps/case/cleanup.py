from uuid import uuid4
from xml.etree import cElementTree as ElementTree

from django.conf import settings

from casexml.apps.case.const import DEFAULT_CASE_INDEX_IDENTIFIERS, CASE_INDEX_EXTENSION
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseBlock, IndexAttrs
from casexml.apps.case.xform import get_case_updates
from corehq.apps.case_search.models import CLAIM_CASE_TYPE
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CommCareCase


def close_cases(case_ids, domain, user, device_id, case_db=None, synctoken_id=None):
    """
    Close cases by submitting a close forms.

    Accepts submitting user as a user object or a fake system user string.

    See `device_id` parameter documentation at
    `corehq.apps.hqcase.utils.submit_case_blocks`.

    Returns the form id of the closing form.
    """
    if hasattr(user, '_id'):
        user_id = user._id
        username = user.username
    else:
        user_id = user
        username = user

    case_blocks = [ElementTree.tostring(CaseBlock(
        create=False,
        case_id=case_id,
        close=True,
    ).as_xml(), encoding='utf-8').decode('utf-8') for case_id in case_ids]

    submission_extras = {}
    if synctoken_id:
        submission_extras = {
            "last_sync_token": synctoken_id
        }
    return submit_case_blocks(
        case_blocks,
        domain,
        username,
        user_id,
        device_id=device_id,
        case_db=case_db,
        submission_extras=submission_extras
    )[0].form_id


def close_case(case_id, domain, user, device_id):
    return close_cases([case_id], domain, user, device_id)


def rebuild_case_from_forms(domain, case_id, detail):
    """
    Given a case ID, rebuild the entire case state based on all existing forms
    referencing it. Useful when things go wrong or when you need to manually
    rebuild a case after archiving / deleting it
    :param domain: The domain the case belongs to
    :param case_id: The ID of the case to be rebuilt
    :param detail: A CaseTransactionDetail object
    """

    return FormProcessorInterface(domain).hard_rebuild_case(case_id, detail)


def safe_hard_delete(case):
    """
    Hard delete a case - by deleting the case itself as well as all forms associated with it
    permanently from the database.

    Will fail hard if the case has any reverse indices or if any of the forms associated with
    the case also touch other cases.

    This is used primarily for cleaning up system cases/actions (e.g. the location delegate case).
    """
    if not settings.UNIT_TESTING:
        from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
        if not (case.is_deleted or case.type == USER_LOCATION_OWNER_MAP_TYPE):
            raise CommCareCaseError("Attempt to hard delete a live case whose type isn't white listed")

    if case.reverse_indices:
        raise CommCareCaseError("You can't hard delete a case that has other dependencies ({})!".format(case.case_id))
    interface = FormProcessorInterface(case.domain)
    forms = interface.get_case_forms(case.case_id)
    for form in forms:
        case_updates = get_case_updates(form)
        if any([c.id != case.case_id for c in case_updates]):
            raise CommCareCaseError("You can't hard delete a case that has shared forms with other cases!")

    interface.hard_delete_case_and_forms(case, forms)


def claim_case(domain, restore_user, host_id, host_type=None, host_name=None, device_id=None):
    """
    Claim a case identified by host_id for claimant identified by owner_id.

    Creates an extension case so that the claimed case is synced to the claimant's device.
    """
    claim_id = uuid4().hex
    if not (host_type and host_name):
        case = CommCareCase.objects.get_case(host_id, domain)
        host_type = case.type
        host_name = case.name
    identifier = DEFAULT_CASE_INDEX_IDENTIFIERS[CASE_INDEX_EXTENSION]
    claim_case_block = CaseBlock(
        create=True,
        case_id=claim_id,
        case_name=host_name,
        case_type=CLAIM_CASE_TYPE,
        owner_id=restore_user.user_id,
        index={
            identifier: IndexAttrs(
                case_type=host_type,
                case_id=host_id,
                relationship=CASE_INDEX_EXTENSION,
            )
        }
    ).as_xml()
    submission_extras = {}
    if restore_user.request_user:
        submission_extras["auth_context"] = AuthContext(
            domain=domain,
            user_id=restore_user.request_user_id,
            authenticated=True
        )
    submit_case_blocks(
        [ElementTree.tostring(claim_case_block, encoding='utf-8').decode('utf-8')],
        domain=domain,
        submission_extras=submission_extras,
        username=restore_user.full_username,
        user_id=restore_user.user_id,
        device_id=device_id,
    )
    return claim_id


def get_first_claims(domain, user_id, case_ids):
    """
    Returns the first claim by user_id of case_ids, or None
    """
    case_ids_found = CommCareCase.objects.get_case_ids_that_exist(domain, case_ids)
    cases_not_found = [case for case in case_ids if case not in case_ids_found]

    if len(cases_not_found) != 0:
        raise CaseNotFound(", ".join(cases_not_found))

    potential_claim_cases = CommCareCase.objects.get_reverse_indexed_cases(
        domain, case_ids_found, case_types=[CLAIM_CASE_TYPE], is_closed=False)

    def _get_host_case_id(case):
        """The actual index identifier is irrelevant so return the referenced case ID
        from the first live extension index"""
        for index in case.live_indices:
            if index.relationship == CASE_INDEX_EXTENSION:
                return index.referenced_id

    previously_claimed_ids = {
        _get_host_case_id(case) for case in potential_claim_cases
        if case.owner_id == user_id
    }

    return set(case_id for case_id in previously_claimed_ids if case_id)
