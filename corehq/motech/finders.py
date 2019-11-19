from datetime import timedelta
from operator import eq

from Levenshtein._levenshtein import distance
from couchdbkit.ext.django.schema import (
    DecimalProperty,
    ListProperty,
    StringProperty,
)
from dateutil.parser import parse as parse_date

from dimagi.ext.couchdbkit import DocumentSchema


def le_days_diff(max_days, date1, date2):
    """
    Returns True if date1 is less than or equal to max_days away from
    date2, otherwise returns False

    >>> from datetime import date
    >>> le_days_diff(364, '2018-01-01', '2017-01-20')
    True
    >>> le_days_diff(364, date(2017, 1, 20), date(2018, 1, 1))
    True
    >>> le_days_diff(364, '2018-01-01', '2020-01-20')
    False

    """
    if isinstance(date1, str):
        date1 = parse_date(date1)
    if isinstance(date2, str):
        date2 = parse_date(date2)
    return abs(date1 - date2) <= timedelta(max_days)


def le_levenshtein_percent(percent, string1, string2):
    """
    Returns True if Levenshtein distance between string1 and string2,
    divided by max length, is less than or equal to the given percent.

    :param percent: Percent expressed as a decimal between 0 and 1
    :param string1: First string to compare
    :param string2: Second string to compare
    :return: True or False

    >>> le_levenshtein_percent(0.2, 'Riyaz', 'Riaz')
    True
    >>> le_levenshtein_percent(0.2, 'Riyaz', 'Riazz')
    False

    """
    if not 0 <= percent < 1:
        raise ValueError('percent must be greater that or equal to 0 and less than 1')
    dist = distance(string1, string2)
    max_len = max(len(string1), len(string2))
    return dist / max_len <= percent


MATCH_TYPE_EXACT = 'exact'
MATCH_TYPE_LEVENSHTEIN = 'levenshtein'  # Useful for words translated across alphabets
MATCH_TYPE_DAYS_DIFF = 'days_diff'  # Useful for estimated dates of birth
MATCH_FUNCTIONS = {
    MATCH_TYPE_EXACT: eq,
    MATCH_TYPE_LEVENSHTEIN: le_levenshtein_percent,
    MATCH_TYPE_DAYS_DIFF: le_days_diff,
}
MATCH_TYPES = tuple(MATCH_FUNCTIONS)
MATCH_TYPE_DEFAULT = MATCH_TYPE_EXACT


class PropertyWeight(DocumentSchema):
    case_property = StringProperty()
    weight = DecimalProperty()
    match_type = StringProperty(required=False, choices=MATCH_TYPES, default=MATCH_TYPE_DEFAULT)
    match_params = ListProperty(required=False)
