import collections
import re

from django.utils.translation import ugettext as _

from corehq.apps.userreports.exceptions import InvalidSQLColumnNameError


def localize(value, lang):
    """
    Localize the given value.

    This function is intended to be used within UCR to localize user supplied
    translations.

    :param value: A dict-like object or string
    :param lang: A language code.
    """
    if isinstance(value, collections.Mapping) and len(value):
        return (
            value.get(lang, None) or
            value.get(default_language(), None) or
            value[sorted(value.keys())[0]]
        )
    return value


def default_language():
    return "en"


def validate_sql_column_name(s):
    if not isinstance(s, unicode):
        s = unicode(s, "utf-8")
    # http://stackoverflow.com/questions/954884/what-special-characters-are-allowed-in-t-sql-column-name
    if not re.match(r'^(?=[\w@#])(?=\D)[\w@#$]+$', s, re.UNICODE):
        raise InvalidSQLColumnNameError(_(u'"{0}" is not a valid SQL column name').format(s))
