from __future__ import absolute_import
from xml.etree import ElementTree
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import get_case_xform_ids
from casexml.apps.case.xform import get_case_updates
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.couch.update_strategy import ActionsUpdateStrategy
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from couchforms import fetch_and_wrap_form


def close_case(case_id, domain, user):
    """
    Close a case by submitting a close form to it.

    Accepts submitting user as a user object or a fake system user string.

    Returns the form id of the closing form.
    """

    if hasattr(user, '_id'):
        user_id = user._id
        username = user.username
    else:
        user_id = user
        username = user

    case_block = ElementTree.tostring(CaseBlock(
        create=False,
        case_id=case_id,
        close=True,
    ).as_xml())

    return submit_case_blocks([case_block], domain, username, user_id)


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


def safe_hard_delete(case):
    """
    Hard delete a case - by deleting the case itself as well as all forms associated with it
    permanently from the database.

    Will fail hard if the case has any reverse indices or if any of the forms associated with
    the case also touch other cases.

    This is used primarily for cleaning up system cases/actions (e.g. the location delegate case).
    """
    if case.reverse_indices:
        raise CommCareCaseError("You can't hard delete a case that has other dependencies ({})!".format(case._id))
    forms = get_case_forms(case._id)
    for form in forms:
        case_updates = get_case_updates(form)
        if any([c.id != case._id for c in case_updates]):
            raise CommCareCaseError("You can't hard delete a case that has shared forms with other cases!")

    docs = [case._doc] + [f._doc for f in forms]
    case.get_db().bulk_delete(docs)


def get_case_forms(case_id):
    """
    Get all forms that have submitted against a case (including archived and deleted forms)
    wrapped by the appropriate form type.
    """
    form_ids = get_case_xform_ids(case_id)
    return [fetch_and_wrap_form(id) for id in form_ids]
