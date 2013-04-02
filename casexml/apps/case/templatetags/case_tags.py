from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import escape

import datetime
import pytz
from casexml.apps.case.models import CommCareCase
from django.template.loader import render_to_string
from corehq.apps.reports.templatetags.timezone_tags import utc_to_timezone
from django.template.defaultfilters import yesno

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

register = template.Library()

DYNAMIC_PROPERTIES_COLUMNS = 4

@register.simple_tag
def render_table(name, rows, collapsible=False):
    return render_to_string("case/partials/property_table.html", {
        "name": name,
        "rows": rows,
        "num_columns": max(map(len, rows)) if rows else None
    })

@register.simple_tag
def render_case(case, timezone=pytz.utc, display=None):
    if isinstance(case, basestring):
        # we were given an ID, fetch the case
        case = CommCareCase.get(case)

    display = display or {
        'layout': [
            # first box
            ("Basic Data", [
                # first row
                [
                    ("Name", "name"),
                    ("Closed?", "closed"),
                ],
                # second row
                [
                    ("Type", "type"),
                    ("External ID", "external_id"),
                ],
                [
                    ("Case ID", "case_id"),
                    ("Domain", "domain"),
                ],
            ]),
            # second box
            ("Submission Info", [
                [
                    ("User ID", "user_id"),
                    ("Owner ID", "owner_id")
                ],
                [
                    ("Opened On", "opened_on"),
                    ("Modified On", "modified_on"),
                ],
                [
                    ("Closed On", "closed_on"),
                ],
            ])
        ],
        'meta': {
            '_date': {
                'process': 'utc_to_timezone'
            },
            'closed': {
                'process': 'yesno'
            },
            'type': {
                'format': '<code>{0}</code>'
            },
            'user_id': {
                'format': '<span data-field="user_id">{0}</span>'
            },
            'owner_id': {
                'format': '<span data-field="owner_id">{0}</span>'
            }
        }
    }

    processors = {
        'utc_to_timezone': lambda d: utc_to_timezone(d, timezone=timezone),
        'yesno': yesno
    }

    layout = display['layout']
    meta = display['meta']


    def display_value(case, prop, meta):
        val = getattr(case, prop, None)

        if prop in meta:
            prop_meta = meta[prop]
        elif isinstance(val, datetime.datetime):
            prop_meta = meta.get('_date', {})
        else:
            prop_meta = {}

        if 'process' in prop_meta:
            val = processors[prop_meta['process']](val)
        val = escape(val)

        if 'format' in prop_meta:
            val = mark_safe(prop_meta['format'].format(val))

        return val


    def set_colspan(rows):
        if not rows:
            return

        max_row_length = max(map(len, rows))

        # set colspan for last element in row if necessary
        for row in rows:
            if len(row) < max_row_length:
                colspan = (max_row_length - len(row)) * 2 + 1
                row.append([None, colspan, None])
   
    seen_properties = []
    default_properties = []

    for section_name, rows in layout:
        processed_rows = []

        for row in rows:
            processed_row = []

            for name, prop in row:
                # raw property name, property name, property value, colspan
                processed_row.append(
                    [prop, _(name), display_value(case, prop, meta)])
                seen_properties.append(prop)

            processed_rows.append(processed_row)

        set_colspan(processed_rows)

        default_properties.append((
            _(section_name) if section_name else "", processed_rows))

    unseen_dynamic_properties = [k for (k, v) 
            in case.dynamic_case_properties() 
            if k not in seen_properties]

    dynamic_properties_rows = []
    for properties in chunks(unseen_dynamic_properties, DYNAMIC_PROPERTIES_COLUMNS):
        row = []

        for prop in properties:
            row.append([prop, prop, display_value(case, prop, meta)])

        dynamic_properties_rows.append(row)

    set_colspan(dynamic_properties_rows)
    
    return render_to_string("case/partials/single_case.html", {
        "default_properties": default_properties,
        "dynamic_properties": dynamic_properties_rows,
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
    
