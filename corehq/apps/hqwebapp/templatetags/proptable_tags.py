"""
A collection of templatetags and helper functions for declaratively defining a
property table layout with multiple (optionally named) tables of some number of
rows of possibly differing length, where each row consists of a number of names
and values which are calculated based on an expression and a data source.

Supports psuedo-tables using dls and real tables.

"""

import collections
import datetime

import attr
from django import template
from django.template.defaultfilters import yesno
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe
from django.utils.html import format_html, format_html_join

import pytz
from jsonobject.exceptions import BadValueError

from dimagi.ext.jsonobject import DateProperty
from dimagi.utils.dates import safe_strftime

from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import pretty_doc_info
from corehq.const import USER_DATE_FORMAT, USER_DATETIME_FORMAT
from corehq.util.dates import iso_string_to_datetime
from corehq.util.timezones.conversions import PhoneTime, ServerTime


class DisplayProcessor(collections.namedtuple("DisplayProcessor", "processor, returns_html")):
    def __call__(self, value, data):
        return self.processor(value, data)


VALUE_DISPLAY_PROCESSORS = {
    'date': DisplayProcessor(lambda value, data: _parse_date_or_datetime(value), False),
    'yesno': DisplayProcessor(lambda value, data: conditional_escape(yesno(value)), False),
    'doc_info': DisplayProcessor(lambda value, data: pretty_doc_info(
        get_doc_info_by_id(data['domain'], value)
    ), True)
}

register = template.Library()


def _is_list_like(val):
    return isinstance(val, collections.Iterable) and not isinstance(val, str)


def _parse_date_or_datetime(val):
    def parse():
        if not val:
            return None

        # datetime is a subclass of date
        if isinstance(val, datetime.date) or not isinstance(val, str):
            return val

        try:
            dt = iso_string_to_datetime(val)
        except ValueError:
            try:
                return DateProperty().wrap(val)
            except BadValueError:
                return val
        else:
            if not any([dt.hour, dt.minute, dt.second, dt.microsecond]):
                return dt.date()
            else:
                return dt
    try:
        result = parse()
        if isinstance(result, datetime.datetime):
            assert result.tzinfo is None
        return result
    except Exception:
        # ignore exceptions from date parsing
        pass


def _format_slug_string_for_display(key):
    return key.replace('_', ' ').replace('-', ' ')


def _to_html(val, key=None, level=0):
    """
    Recursively convert a value to its HTML representation using <dl>s for
    dictionaries and <ul>s for lists.
    """
    def _recurse(k, v):
        return _to_html(v, key=k, level=level + 1)

    def _key_format(k, v):
        if not _is_list_like(v):
            return _format_slug_string_for_display(k)
        else:
            return ""

    if isinstance(val, dict):
        ret = format_html(
            "<dl {}>{}</dl>",
            mark_safe("class='well'") if level == 0 else '',  # nosec: no user input
            format_html_join(
                "",
                "<dt>{}</dt><dd>{}</dd>",
                [(_key_format(k, v), _recurse(k, v)) for k, v in val.items()]
            )
        )

    elif _is_list_like(val):
        ret = format_html(
            "<dl>{}</dl>",
            format_html_join("", "<dt>{}</dt><dd>{}</dd>", [(key, _recurse(None, v)) for v in val])
        )

    elif isinstance(val, datetime.date):
        if isinstance(val, datetime.datetime):
            fmt = USER_DATETIME_FORMAT
        else:
            fmt = USER_DATE_FORMAT

        iso = val.isoformat()
        ret = format_html("<time title='{title}' datetime='{iso}'>{display}</time>".format(
            title=iso,
            iso=iso,
            display=safe_strftime(val, fmt)
        ))
    else:
        if val is None:
            val = '---'

        ret = escape(val)

    return ret


@attr.s
class DisplayConfig:
    # dict key or callable to get value from data dict
    expr = attr.ib()

    # name of the field. Defaults to the value `expr` if not given.
    name = attr.ib(default=None)

    description = attr.ib(default=None)

    # processor to apply. Available processors are:
    # - 'yesno': convert boolean values to yes / no / maybe
    # - 'doc_info': render a DocInfo
    # - 'date': convert date strings to date objects
    process = attr.ib(default=None)

    # String to use as the output format e.g. "<b>{}</b>"
    format = attr.ib(default=None)

    # property that is passed through in the return result
    has_history = attr.ib(default=False)

    # True if this value represents a 'phone time'. See ``PhoneTime``
    is_phone_time = attr.ib(default=False)

    @process.validator
    def _validate_process(self, attribute, value):
        choices = VALUE_DISPLAY_PROCESSORS.keys()
        if value is not None and value not in choices:
            raise ValueError("'process' must be one of {}".format(", ".join(choices)))


def get_display_data(data: dict, prop_def: DisplayConfig, timezone=pytz.utc):
    expr_name = _get_expr_name(prop_def)
    name = prop_def.name or _format_slug_string_for_display(expr_name)

    val = eval_expr(prop_def.expr, data)

    processor = VALUE_DISPLAY_PROCESSORS.get(prop_def.process, None)
    if processor:
        try:
            val = processor(val, data)
        except Exception:
            # ignore exceptions from date parsing
            pass
    if isinstance(val, datetime.datetime):
        if not prop_def.is_phone_time:
            val = ServerTime(val).user_time(timezone).done()
        else:
            val = PhoneTime(val, timezone).user_time(timezone).done()

    if not processor or not processor.returns_html:
        val = _to_html(val)

    if prop_def.format:
        val = format_html(prop_def.format, val)

    return {
        "expr": expr_name,
        "name": name,
        "description": prop_def.description,
        "value": val,
        "has_history": prop_def.has_history,
    }


def _get_expr_name(prop_def: DisplayConfig):
    if callable(prop_def.expr):
        return prop_def.name
    else:
        return prop_def.expr


def eval_expr(expr, dict_data):
    """
    If expr is a string, will do a dict lookup using that string as a key.

    If expr is a callable, will call it on the dict.
    """
    if callable(expr):
        return expr(dict_data)
    else:
        return dict_data.get(expr, None)


def get_table_as_rows(data, definition, timezone=pytz.utc):
    """
    Return a low-level definition of a table, given a data object and
    a high-level declarative definition of the table rows and value
    calculations.

    :param definition: dict with keys:
       "layout": list of rows to display. Each row must be a list of `DisplayConfig` classes
            that represent the cells of the row.
    """
    rows = [
        [get_display_data(data, prop, timezone=timezone) for prop in row]
        for row in definition['layout']
    ]

    max_row_len = max(list(map(len, rows))) if rows else 0
    for row in rows:
        if len(row) < max_row_len:
            row.append({
                "colspan": 2 * (max_row_len - len(row))
            })

    return rows
