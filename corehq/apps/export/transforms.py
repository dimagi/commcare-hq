from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.cache import cache

from corehq.apps.export.esaccessors import get_case_name
from corehq.apps.users.util import cached_user_id_to_username, cached_owner_id_to_display
from corehq.util import reverse

"""
Module for transforms used in exports.
"""


def case_close_to_boolean(value, doc):
    return str(value is not None)


def user_id_to_username(user_id, doc):
    return cached_user_id_to_username(user_id)


def owner_id_to_display(owner_id, doc):
    return cached_owner_id_to_display(owner_id)


def case_id_to_case_name(case_id, doc):
    return _cached_case_id_to_case_name(case_id)


def case_id_to_link(case_id, doc):
    from corehq.apps.reports.views import CaseDataView
    return reverse(CaseDataView.urlname, args=[doc['domain'], case_id], absolute=True)


def form_id_to_link(form_id, doc):
    from corehq.apps.reports.views import FormDataView
    return reverse(FormDataView.urlname, args=[doc['domain'], form_id], absolute=True)


def case_or_user_id_to_name(id, doc):
    if doc['couch_recipient_doc_type'] == 'CommCareCase':
        return case_id_to_case_name(id, doc)
    elif doc['couch_recipient_doc_type'] in ('CommCareUser', 'WebUser'):
        return user_id_to_username(id, doc)


def workflow_transform(workflow, doc):
    from corehq.apps.sms.models import WORKFLOWS_FOR_REPORTS
    from corehq.apps.sms.filters import MessageTypeFilter

    types = []
    if workflow in WORKFLOWS_FOR_REPORTS:
        types.append(workflow.lower())
    if doc.get('xforms_session_couch_id', None):
        types.append(MessageTypeFilter.OPTION_SURVEY.lower())
    if not types:
        types.append(MessageTypeFilter.OPTION_OTHER.lower())
    return ', '.join(types)


def doc_type_transform(doc_type, doc):
    doc_types = {
        "CommCareUser": "Mobile Worker",
        "WebUser": "Web User",
        "CommCareCase": "Case",
    }
    return doc_types.get(doc_type, "Unknown")


NULL_CACHE_VALUE = "___NULL_CACHE_VAL___"


def _cached_case_id_to_case_name(case_id):
    if not case_id:
        return None
    key = 'case_id_to_case_name_cache_{id}'.format(id=case_id)
    ret = cache.get(key, NULL_CACHE_VALUE)
    if ret != NULL_CACHE_VALUE:
        return ret
    case_name = get_case_name(case_id)
    cache.set(key, case_name, 2 * 60 * 60)
    return case_name
