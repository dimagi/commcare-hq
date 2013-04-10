import copy
from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import escape

import datetime
import pytz
import dateutil
from django.template.loader import render_to_string
import simplejson
from dimagi.utils.timezones.utils import adjust_datetime_to_timezone
from django.template.defaultfilters import yesno

import itertools
import types
import collections

from couchforms.templatetags.xform_tags import SYSTEM_FIELD_NAMES
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case import const

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

register = template.Library()

DYNAMIC_CASE_PROPERTIES_COLUMNS = 4
FORM_PROPERTIES_COLUMNS = 2


def get_display(val, dt_format="%b %d, %Y %H:%M %Z", timezone=pytz.utc,
                parse_dates=True):
    recurse = lambda v: get_display(v, dt_format=dt_format, timezone=timezone)

    if isinstance(val, types.DictionaryType):
        ret = "".join(
            ["<dl>"] + 
            ["<dt>{0}</dt><dd>{1}</dd>".format(k, recurse(v))
             for k, v in val.items()] +
            ["</dl>"])

    elif (isinstance(val, collections.Iterable) and 
          not isinstance(val, basestring)):
        ret = "".join(
            ["<ul>"] +
            ["<li>{0}</li>".format(recurse(v)) for v in val] +
            ["</ul>"])

    else:
        if isinstance(val, datetime.datetime):
            val = val.strftime(dt_format)

        ret = escape(val)

    return mark_safe(ret)


def build_tables(data, definition, processors=None, timezone=pytz.utc):
    default_processors = {
        'yesno': yesno
    }
    processors = processors or {}
    processors.update(default_processors)

    def get_value(data, expr):
        # todo: nested attributes, support for both getitem and getattr

        return data.get(expr, None)

    def get_display_tuple(prop):
        expr = prop['expr']
        name = prop.get('name', expr)
        format = prop.get('format')
        process = prop.get('process')
        parse_date = prop.get('parse_date')

        val = get_value(data, expr)

        if parse_date and not isinstance(val, datetime.datetime):
            try:
                val = dateutil.parser.parse(val)
            except:
                if not val:
                    val = '---'

        if isinstance(val, datetime.datetime):
            if val.tzinfo is None:
                val = val.replace(tzinfo=pytz.utc)

            val = adjust_datetime_to_timezone(val, val.tzinfo, timezone.zone)


        if process:
            val = escape(processors[process](val))
        else:
            val = mark_safe(get_display(val, timezone=timezone))

        if format:
            val = mark_safe(format.format(val))

        return (expr, name, val)

    sections = []

    for section_name, rows in definition:
        processed_rows = [[get_display_tuple(prop) for prop in row]
                          for row in rows]

        columns = list(itertools.izip_longest(*processed_rows))
        sections.append((_(section_name) if section_name else "", columns))

    return sections


@register.simple_tag
def render_tables(tables, collapsible=False):
    return render_to_string("case/partials/property_table.html", {
        "tables": tables
    })


def get_definition(keys, num_columns=FORM_PROPERTIES_COLUMNS):
    return [
        (None, 
         chunks([{"expr": prop} for prop in sorted(keys)], num_columns))
    ]


@register.simple_tag
def render_form(form, timezone=pytz.utc, display=None, case_id=None):
    def key_filter(key):
        if key in SYSTEM_FIELD_NAMES:
            return False

        if any(key.startswith(p) for p in ['#', '@', '_']):
            return False

        return True

    # Form Data tab
    form_dict = copy.deepcopy(form.top_level_tags())
    form_keys = [k for k in form_dict.keys() if key_filter(k)]
    form_data = build_tables(form_dict, definition=get_definition(form_keys),
            timezone=timezone)

    # Case tab
    this_case_block = None
    other_cases_blocks = []

    for block in extract_case_blocks(form):
        if block.get("@%s" % const.CASE_TAG_ID) == case_id:
            this_case_block = block
        else:
            other_cases_blocks.append(block)
   
    if this_case_block:
        this_case_data = build_tables( 
                this_case_block,
                definition=get_definition(this_case_block.keys()),
                timezone=timezone)
    else:
        this_case_data = None

    if other_cases_blocks:
        other_cases_data = [build_tables(
                b, definition=get_definition(b.keys()), timezone=timezone)
                for b in other_cases_blocks]
    else:
        other_cases_data = None
  
    # Meta tab
    meta = form_dict.pop('meta')
    form_meta_data = build_tables(meta, definition=get_definition(meta.keys()),
            timezone=timezone)

    return render_to_string("case/partials/single_form.html", {
        "form_data": form_data,
        "form_meta_data": form_meta_data,
        "this_case_data": this_case_data,
        "other_cases_data": other_cases_data,
    })


@register.simple_tag
def render_case(case, timezone=pytz.utc, display=None):
    display = display or [
        (_("Basic Data"), [
            [
                {
                    "expr": "name",
                    "name": _("Name"),
                },
                {
                    "expr": "closed",
                    "name": _("Closed?"),
                    "process": "yesno",
                },
            ],
            [
                {
                    "expr": "type",
                    "name": _("Type"),
                    "format": '<code>{0}</code>',
                },
                {
                    "expr": "external_id",
                    "name": _("External ID"),
                },
            ],
            [
                {
                    "expr": "case_id",
                    "name": _("Case ID"),
                },
                {
                    "expr": "domain",
                    "name": _("Domain"),
                },
            ],
        ]),
        (_("Submission Info"), [
            [
                {
                    "expr": "opened_on",
                    "name": _("Opened On"),
                    "parse_date": True,
                },
                {
                    "expr": "user_id",
                    "name": _("User ID"),
                    "format": '<span data-field="user_id">{0}</span>',
                },
            ],
            [
                {
                    "expr": "modified_on",
                    "name": _("Modified On"),
                    "parse_date": True,
                },
                {
                    "expr": "owner_id",
                    "name": _("Owner ID"),
                    "format": '<span data-field="owner_id">{0}</span>',
                },
            ],
            [
                {
                    "expr": "closed_on",
                    "name": _("Closed On"),
                    "parse_date": True,
                },
            ],
        ])
    ]

    data = copy.deepcopy(case.to_json())
    default_properties = build_tables(
            data, definition=display, timezone=timezone)

    dynamic_data = dict((k, v) for (k, v) in case.dynamic_case_properties()
                        if k in data)
    dynamic_keys = sorted(dynamic_data.keys())
    definition = [
        (None, chunks(
            [{"expr": prop} for prop in dynamic_keys],
            DYNAMIC_CASE_PROPERTIES_COLUMNS)
        )
    ]

    dynamic_properties = build_tables(
            dynamic_data, definition=definition, timezone=timezone)

    actions = case.to_json()['actions']
    actions.reverse()

    return render_to_string("case/partials/single_case.html", {
        "default_properties": default_properties,
        "dynamic_properties": dynamic_properties,
        "case": case,
        "case_actions": mark_safe(simplejson.dumps(actions)),
        "timezone": timezone
    })
    
    
@register.simple_tag
def case_inline_display(case):
    """
    Given a case id, make a best effort at displaying it.
    """
    if case:
        if case.opened_on:
            return "%s (opened: %s)" % (case.name, case.opened_on.date())
        else:
            return case.name
    return "empty case" 
    
