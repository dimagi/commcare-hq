from __future__ import absolute_import
import logging
from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound
from datetime import datetime
from casexml.apps.case import const
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.util import get_case_xform_ids, primary_actions
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml import V2
from casexml.apps.case.xml.parser import KNOWN_PROPERTIES
from corehq.apps.hqcase.utils import submit_case_blocks
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
        version=V2,
    ).as_xml())

    return submit_case_blocks([case_block], domain, username, user_id)


def _get_actions_from_forms(sorted_forms, case_id):
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
    return case_actions, domain


def rebuild_case_from_actions(case, actions, all_form_ids):
    reset_state(case)
    # in addition to resetting the state, also manually clear xform_ids and actions
    # since we're going to rebuild these from the forms
    case.xform_ids = []

    case.actions = actions
    # call "rebuild" on the case, which should populate xform_ids
    # and re-sort actions if necessary
    case.rebuild(strict=False)
    # don't swallow stock-only xform_ids during case rebuilds
    case.xform_ids = case.xform_ids + [form_id for form_id in all_form_ids
                                       if form_id not in case.xform_ids]


def rebuild_case(case_id):
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

    rebuild_case_from_actions(case, actions, [f.get_id for f in sorted_forms])
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


def reset_state(case):
    """
    Clear known case properties, and all dynamic properties
    """
    dynamic_properties = set([k for action in case.actions for k in action.updated_unknown_properties.keys()])
    for k in dynamic_properties:
        try:
            delattr(case, k)
        except KeyError:
            pass
        except AttributeError:
            # 'case_id' is not a valid property so don't worry about spamming
            # this error.
            if k != 'case_id':
                logging.error(
                    "Cannot delete attribute '%(attribute)s' from case '%(case_id)s'" % {
                        'case_id': case._id,
                        'attribute': k,
                    }
                )

    # already deleted means it was explicitly set to "deleted",
    # as opposed to getting set to that because it has no actions
    already_deleted = case.doc_type == 'CommCareCase-Deleted' and primary_actions(case)
    if not already_deleted:
        case.doc_type = 'CommCareCase'

    # hard-coded normal properties (from a create block)
    for prop, default_value in KNOWN_PROPERTIES.items():
        setattr(case, prop, default_value)

    case.closed = False
    case.modified_on = None
    case.closed_on = None
    case.closed_by = ''
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
