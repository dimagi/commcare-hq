from __future__ import absolute_import
from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound
from datetime import datetime
from casexml.apps.case import const
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.util import get_case_xform_ids
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml import V2
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.couch.update_strategy import ActionsUpdateStrategy
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


def _get_actions_from_forms(sorted_forms, case_id):
    from corehq.apps.commtrack.processing import get_stock_actions
    case_actions = []
    domain = None
    for form in sorted_forms:
        if domain is None:
            domain = form.domain
        assert form.domain == domain

        case_updates = get_case_updates(form)
        filtered_updates = [u for u in case_updates if u.id == case_id]
        for u in filtered_updates:
            case_actions.extend(u.get_case_actions(form))
        stock_actions = get_stock_actions(form)
        case_actions.extend([intent.action
                             for intent in stock_actions.case_action_intents
                             if not intent.is_deprecation])
    return case_actions, domain


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


def rebuild_case_from_forms(case_id):
    """
    Given a case ID, rebuild the entire case state based on all existing forms
    referencing it. Useful when things go wrong or when you need to manually
    rebuild a case after archiving / deleting it
    """

    try:
        case = CommCareCase.get(case_id)
        found = True
    except ResourceNotFound:
        case = CommCareCase()
        case._id = case_id
        found = False

    forms = get_case_forms(case_id)
    filtered_forms = [f for f in forms if f.doc_type == "XFormInstance"]
    sorted_forms = sorted(filtered_forms, key=lambda f: f.received_on)

    actions, domain = _get_actions_from_forms(sorted_forms, case_id)

    if not found and case.domain is None:
        case.domain = domain

    rebuild_case_from_actions(case, actions)
    # todo: should this move to case.rebuild?
    if not case.xform_ids:
        if not found:
            return None
        # there were no more forms. 'delete' the case
        case.doc_type = 'CommCareCase-Deleted'

    # add a "rebuild" action
    case.actions.append(_rebuild_action())
    case.save()
    return case


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


def _rebuild_action():
    now = datetime.utcnow()
    return CommCareCaseAction(
        action_type=const.CASE_ACTION_REBUILD,
        date=now,
        server_date=now,
    )
