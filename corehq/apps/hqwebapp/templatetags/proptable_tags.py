"""
A collection of templatetags and helper functions for declaratively defining a
property table layout with multiple (optionally named) tables of some number of
rows of possibly differing length, where each row consists of a number of names
and values which are calculated based on an expression and a data source.

Supports psuedo-tables using dls (heights are adjusted using JavaScript) and
real tables.

See render_case() in casexml for an example of the display definition format.

"""

import collections
import datetime
import itertools
import logging
import types

import dateutil
import pytz

from django import template
from django.template.defaultfilters import yesno
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.html import escape, conditional_escape
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import pretty_doc_info
from corehq.const import USER_DATETIME_FORMAT, USER_DATE_FORMAT
from corehq.util.timezones.conversions import ServerTime

register = template.Library()


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def is_list(val):
    return (isinstance(val, collections.Iterable) and 
            not isinstance(val, basestring))

def parse_date_or_datetime(val):
    """A word to the wise: datetime is a subclass of date"""
    if isinstance(val, datetime.date):
        return val
    try:
        dt = dateutil.parser.parse(val)
        if not any([dt.hour, dt.minute, dt.second, dt.microsecond]):
            return dt.date()
        else:
            return dt
    except Exception:
        return val if val else None


def to_html(key, val, level=0, datetime_fmt=USER_DATETIME_FORMAT,
            date_fmt=USER_DATE_FORMAT, timeago=False, timezone=pytz.utc,
            key_format=None, collapse_lists=False):
    """
    Recursively convert a value to its HTML representation using <dl>s for
    dictionaries and <ul>s for lists.
    """
    recurse = lambda k, v: to_html(k, v, level=level + 1,
            datetime_fmt=datetime_fmt, date_fmt=date_fmt, timeago=timeago,
            timezone=timezone, key_format=key_format,
            collapse_lists=collapse_lists)
    
    def _key_format(k, v):
        if not is_list(v):
            return key_format(k) if key_format else k
        else:
            return ""

    def safe_strftime(val, fmt):
        """
        This hack assumes datetime_fmt does not contain directives whose
        value is dependent on the year, such as week number of the year ('%W').
        The hack allows strftime to be used to support directives such as '%b'.
        """
        if isinstance(val, datetime.datetime):
            safe_val = datetime.datetime(2012, val.month, val.day, hour=val.hour,
                                         minute=val.minute, second=val.second,
                                         microsecond=val.microsecond, tzinfo=val.tzinfo)
        else:
            safe_val = datetime.date(2012, val.month, val.day)
        return safe_val.strftime(fmt.replace("%Y", str(val.year)))


    if isinstance(val, types.DictionaryType):
        ret = "".join(
            ["<dl %s>" % ("class='well'" if level == 0 else '')] + 
            ["<dt>%s</dt><dd>%s</dd>" % (
                _key_format(k, v), recurse(k, v)
             ) for k, v in val.items()] +
            ["</dl>"])

    elif is_list(val):
        if collapse_lists:
            ret = "".join(
                ["<dl>"] +
                ["<dt>%s</dt><dd>%s</dd>" % (key, recurse(None, v)) for v in val] +
                ["</dl>"])
        else:
            ret = "".join(
                ["<ul>"] +
                ["<li>%s</li>" % recurse(None, v) for v in val] +
                ["</ul>"])

    elif isinstance(val, datetime.date):
        if isinstance(val, datetime.datetime):
            fmt = datetime_fmt
        else:
            fmt = date_fmt

        iso = val.isoformat()
        ret = mark_safe("<time %s title='%s' datetime='%s'>%s</time>" % (
            "class='timeago'" if timeago else "", iso, iso, safe_strftime(val, fmt)))
    else:
        if val is None or val == '':
            val = '---'

        ret = escape(val)

    return mark_safe(ret)


def get_display_data(data, prop_def, processors=None, timezone=pytz.utc):
    # when prop_def came from a couchdbkit document, it will be a LazyDict with
    # a broken pop method.  This conversion also has the effect of a shallow
    # copy, which we want.
    prop_def = dict(prop_def)

    default_processors = {
        'yesno': yesno,
        'doc_info': lambda value: pretty_doc_info(
            get_doc_info_by_id(data['domain'], value)
        )
    }
    processors = processors or {}
    processors.update(default_processors)

    def format_key(key):
        key = key.replace('_', ' ')
        return key.replace('-', ' ')

    expr = prop_def.pop('expr')
    name = prop_def.pop('name', format_key(expr))
    format = prop_def.pop('format', None)
    process = prop_def.pop('process', None)

    # todo: nested attributes, jsonpath, indexing into related documents
    val = data.get(expr, None)

    if prop_def.pop('parse_date', None):
        val = parse_date_or_datetime(val)
    is_utc = prop_def.pop('is_utc', True)
    if isinstance(val, datetime.datetime):
        if is_utc:
            logging.error("is_utc should really only get passed with "
                          "timezone-naive datetimes representing UTC")
            val = ServerTime(val).user_time(timezone).done()
        else:
            val = val.replace(tzinfo=timezone)

    try:
        val = conditional_escape(processors[process](val))
    except KeyError:
        val = mark_safe(to_html(None, val, 
            timezone=timezone, key_format=format_key, collapse_lists=True,
            **prop_def))
    if format:
        val = mark_safe(format.format(val))

    return {
        "expr": expr,
        "name": name,
        "value": val
    }


def get_tables_as_rows(data, definition, processors=None, timezone=pytz.utc):
    """
    Return a low-level definition of a group of tables, given a data object and
    a high-level declarative definition of the table rows and value
    calculations.

    """

    sections = []

    for section in definition:
        rows = [[get_display_data(data, prop, timezone=timezone, processors=processors)
                 for prop in row] 
                for row in section['layout']]

        max_row_len = max(map(len, rows)) if rows else 0
        for row in rows:
            if len(row) < max_row_len:
                row.append({
                    "colspan": 2 * (max_row_len - len(row))
                })

        sections.append({
            "name": section.get('name') or '',
            "rows": rows
        })

    return sections


def get_tables_as_columns(*args, **kwargs):
    sections = get_tables_as_rows(*args, **kwargs)
    for section in sections:
        section['columns'] = list(itertools.izip_longest(*section['rows']))
        del section['rows']

    return sections


@register.simple_tag
def render_tables(tables, options=None):
    options = options or {}
    id = options.get('id')
    style = options.get('style', 'dl')
    assert style in ('table', 'dl')

    if id is None:
        import uuid
        id = "a" + str(uuid.uuid4())
   
    if style == 'table':
        return render_to_string("hqwebapp/proptable/property_table.html", {
            "tables": tables,
            "id": id
        })

    else:
        adjust_heights = options.get('adjust_heights', True)
        put_loners_in_wells = options.get('put_loners_in_wells', True)

        return render_to_string("hqwebapp/proptable/dl_property_table.html", {
            "tables": tables,
            "id": id,
            "adjust_heights": adjust_heights,
            "put_loners_in_wells": put_loners_in_wells
        })


def get_definition(keys, num_columns=1, name=None):
    """
    Get a default single table layout definition for `keys` split across
    `num_columns` columns.
    
    """
    layout = chunks([{"expr": prop} for prop in keys], num_columns)

    return [
        {
            "name": name,
            "layout": layout
        }
    ]
