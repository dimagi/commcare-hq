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
import types

import dateutil
import pytz

from django import template
from django.template.defaultfilters import yesno
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.html import escape


from dimagi.utils.timezones.utils import adjust_datetime_to_timezone

register = template.Library()


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def is_list(val):
    return (isinstance(val, collections.Iterable) and 
            not isinstance(val, basestring))


def to_html(key, val, dt_format="%b %d, %Y %H:%M %Z", timezone=pytz.utc,
                key_format=None, level=0, collapse_lists=False):
    """
    Recursively convert an object to its HTML representation using <dl>s for
    dictionaries and <ul>s for lists.

    key -- optional key for the object, which determines some formatting
            choices. used when calling recursively.
    val -- the object
    dt_format -- strftime format for datetimes
    key_format -- formatting function to apply to keys
    collapse_lists -- whether to turn "key": [1, 2] into

            <dt>key</dt><dd>1</dd><dt>key</dt><dd>2</dd>

        instead of
    
            <dt>key</dt><dd><ul><li>1</li><li>2</li></ul></dd>
    """

    recurse = lambda k, v: to_html(k, v,
            dt_format=dt_format, timezone=timezone, key_format=key_format,
            level=level + 1, collapse_lists=collapse_lists)
    
    def _key_format(k, v):
        if not is_list(v):
            return key_format(k) if key_format else k
        else:
            return ""

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

    else:
        if isinstance(val, datetime.datetime):
            val = val.strftime(dt_format)

        ret = escape(val)

    return mark_safe(ret)


def get_tables_as_rows(data, definition, processors=None, timezone=pytz.utc):
    """
    Return a low-level definition of a group of tables, given a data object and
    a high-level declarative definition of the table rows and value
    calculations.

    """
    default_processors = {
        'yesno': yesno
    }
    processors = processors or {}
    processors.update(default_processors)

    def get_value(data, expr):
        # todo: nested attributes, jsonpath, indexing into related documents,
        # support for both getitem and getattr

        return data.get(expr, None)

    def format_key(key):
        key = key.replace('_', ' ')
        return key.replace('-', ' ')

    def get_display_data(prop):
        expr = prop['expr']
        name = prop.get('name', format_key(expr))
        format = prop.get('format')
        process = prop.get('process')
        parse_date = prop.get('parse_date')

        val = get_value(data, expr)

        if parse_date and not isinstance(val, datetime.datetime):
            try:
                val = dateutil.parser.parse(val)
            except:
                val = val if val else '---'

        if isinstance(val, datetime.datetime):
            if val.tzinfo is None:
                val = val.replace(tzinfo=pytz.utc)

            val = adjust_datetime_to_timezone(val, val.tzinfo, timezone.zone)

        if process:
            val = escape(processors[process](val))
        else:
            if val is None:
                val = '---'

            val = mark_safe(to_html(None,
                val, timezone=timezone, key_format=format_key,
                collapse_lists=True))

        if format:
            val = mark_safe(format.format(val))

        return {
            "expr": expr,
            "name": name,
            "value": val
        }

    sections = []

    for section in definition:
        rows = [[get_display_data(prop) for prop in row] 
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



