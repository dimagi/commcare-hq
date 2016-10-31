from django.core.cache import cache

from corehq.apps.export.esaccessors import get_case_name
from corehq.apps.users.util import cached_user_id_to_username, cached_owner_id_to_display

"""
Module for transforms used in exports.
"""


def user_id_to_username(user_id, doc, domain):
    return cached_user_id_to_username(user_id)


def owner_id_to_display(owner_id, doc, domain):
    return cached_owner_id_to_display(owner_id)


def case_id_to_case_name(case_id, doc, domain):
    return _cached_case_id_to_case_name(case_id, domain)

NULL_CACHE_VALUE = "___NULL_CACHE_VAL___"


def _cached_case_id_to_case_name(case_id, domain):
    if not case_id:
        return None
    key = 'case_id_to_case_name_cache_{id}'.format(id=case_id)
    ret = cache.get(key, NULL_CACHE_VALUE)
    if ret != NULL_CACHE_VALUE:
        return ret
    case_names = get_case_name(case_id, domain)
    ret = case_names[0]['name'] if case_names else None
    cache.set(key, ret)
    return ret
