import copy
from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import escape

import datetime
import pytz
import dateutil
from casexml.apps.case.models import CommCareCase
from django.template.loader import render_to_string
from dimagi.utils.timezones.utils import adjust_datetime_to_timezone
from django.template.defaultfilters import yesno

import itertools
import types
import collections

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
                pass  # val = val

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

@register.simple_tag
def render_form(form, timezone=pytz.utc, display=None):

    form = dict(copy.deepcopy(form.form))
    case = form.pop('case')
    meta = form.pop('meta')

    display = display or [
        (None, chunks(
            [{"expr": prop} for prop in form],
            FORM_PROPERTIES_COLUMNS)
        )
    ]

    form_data = build_tables(form, definition=display, timezone=timezone)
    
    definition = [
        (None, chunks(
            [{"expr": prop} for prop in case],
            FORM_PROPERTIES_COLUMNS)
        )
    ]

    form_case_data = build_tables(
            case, definition=definition, timezone=timezone)
    
    definition = [
        (None, chunks(
            [{"expr": prop} for prop in meta],
            FORM_PROPERTIES_COLUMNS)
        )
    ]

    form_meta_data = build_tables(meta, definition=definition,
            timezone=timezone)

    return render_to_string("case/partials/single_form.html", {
        "form_data": form_data,
        "form_meta_data": form_meta_data,
        "form_case_data": form_case_data,
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
    definition = [
        (None, chunks(
            [{"expr": prop} for prop in dynamic_data.keys()],
            DYNAMIC_CASE_PROPERTIES_COLUMNS)
        )
    ]

    dynamic_properties = build_tables(
            dynamic_data, definition=definition, timezone=timezone)

    return render_to_string("case/partials/single_case.html", {
        "default_properties": default_properties,
        "dynamic_properties": dynamic_properties,
        "case": case, 
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
    
