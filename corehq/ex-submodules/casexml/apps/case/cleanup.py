from __future__ import absolute_import
from xml.etree import ElementTree
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import get_case_xform_ids
from casexml.apps.case.xform import get_case_updates
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.couch.update_strategy import ActionsUpdateStrategy
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.util.test_utils import unit_testing_only
from couchforms import fetch_and_wrap_form


def close_cases(case_ids, domain, user):
    """
    Close cases by submitting a close forms.

    Accepts submitting user as a user object or a fake system user string.

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
    ).as_xml()) for case_id in case_ids]

    return submit_case_blocks(case_blocks, domain, username, user_id)


def close_case(case_id, domain, user):
    return close_cases([case_id], domain, user)


def rebuild_case_from_actions(case, actions):
    strategy = ActionsUpdateStrategy(case)
    strategy.reset_case_state()
    # in addition to resetting the state, also manually clear xform_ids and actions
    # since we're going to rebuild these from the forms
    case.xform_ids = []

    case.actions = actions
    # call "rebuild" on the case, which should populate xform_ids
    # and re-sort actions if necessary
    strategy.soft_rebuild_case()


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


@unit_testing_only
def safe_hard_delete(case):
    """
    Hard delete a case - by deleting the case itself as well as all forms associated with it
    permanently from the database.

    Will fail hard if the case has any reverse indices or if any of the forms associated with
    the case also touch other cases.

    This is used primarily for cleaning up system cases/actions (e.g. the location delegate case).
    """
    if case.reverse_indices:
        raise CommCareCaseError("You can't hard delete a case that has other dependencies ({})!".format(case.case_id))
    interface = FormProcessorInterface(case.domain)
    forms = interface.get_case_forms(case.case_id)
    for form in forms:
        case_updates = get_case_updates(form)
        if any([c.id != case.case_id for c in case_updates]):
            raise CommCareCaseError("You can't hard delete a case that has shared forms with other cases!")

    interface.bulk_delete(case, forms)
