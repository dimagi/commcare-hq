from django.core.cache import cache

from corehq.apps.export.esaccessors import get_case_name
from corehq.apps.users.util import cached_user_id_to_username, cached_owner_id_to_display

"""
Module for transforms used in exports.
"""


def user_id_to_username(user_id, doc):
    return cached_user_id_to_username(user_id)


def owner_id_to_display(owner_id, doc):
    return cached_owner_id_to_display(owner_id)


def case_id_to_case_name(case_id, doc):
    return _cached_case_id_to_case_name(case_id)


def workflow_transform(workflow, doc):
    from corehq.apps.sms.models import (
        WORKFLOW_REMINDER,
        WORKFLOW_KEYWORD,
        WORKFLOW_BROADCAST,
        WORKFLOW_CALLBACK,
        WORKFLOW_DEFAULT,
        WORKFLOW_FORWARD,
        WORKFLOW_PERFORMANCE,
    )
    from corehq.apps.sms.filters import MessageTypeFilter

    relevant_workflows = [
        WORKFLOW_REMINDER,
        WORKFLOW_KEYWORD,
        WORKFLOW_BROADCAST,
        WORKFLOW_CALLBACK,
        WORKFLOW_PERFORMANCE,
        WORKFLOW_DEFAULT,
    ]
    types = []
    if workflow in relevant_workflows:
        types.append(workflow.lower())
    if doc.get('xforms_session_couch_id', None):
        types.append(MessageTypeFilter.OPTION_SURVEY.lower())
    if not types:
        types.append(MessageTypeFilter.OPTION_OTHER.lower())
    return ', '.join(types)


NULL_CACHE_VALUE = "___NULL_CACHE_VAL___"


def _cached_case_id_to_case_name(case_id):
    if not case_id:
        return None
    key = 'case_id_to_case_name_cache_{id}'.format(id=case_id)
    ret = cache.get(key, NULL_CACHE_VALUE)
    if ret != NULL_CACHE_VALUE:
        return ret
    case_name = get_case_name(case_id)
    cache.set(key, case_name)
    return case_name
