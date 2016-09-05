from couchdbkit import ResourceNotFound
from django.core.cache import cache
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.util import cached_user_id_to_username, cached_owner_id_to_display
from corehq.util.dates import iso_string_to_datetime
from corehq.util.timezones.utils import get_timezone_aware_date_for_domain

EXCEL_FORMAT = '%Y-%m-%d %H:%M:%S'


"""
Module for transforms used in exports.
"""


def user_id_to_username(user_id, doc):
    return cached_user_id_to_username(user_id)


def owner_id_to_display(owner_id, doc):
    return cached_owner_id_to_display(owner_id)


def case_id_to_case_name(case_id, doc):
    return _cached_case_id_to_case_name(case_id)

NULL_CACHE_VALUE = "___NULL_CACHE_VAL___"


def _cached_case_id_to_case_name(case_id):
    key = 'case_id_to_case_name_cache_{id}'.format(id=case_id)
    ret = cache.get(key, NULL_CACHE_VALUE)
    if ret != NULL_CACHE_VALUE:
        return ret
    try:
        case = CommCareCase.get_lite(case_id)
        ret = case['name'] if "name" in case else None
    except ResourceNotFound:
        ret = None
    cache.set(key, ret)
    return ret


def transform_date_to_domain_timezone(domain, value, doc, excel_format=False):
    """
    Transforms a date based on the current domain's timezone.
    If transform_dates is True then the date is formatted for
    excel. If it cannot be parsed, it just returns the value.
    """

    if not value:
        return value

    try:
        date_value = iso_string_to_datetime(value, strict=True)
    except ValueError:
        # Most likely not a date
        return value

    date_value_aware = get_timezone_aware_date_for_domain(domain, date_value)

    if excel_format:
        value = date_value_aware.strftime(EXCEL_FORMAT)
    else:
        value = date_value_aware.isoformat()

    return value
