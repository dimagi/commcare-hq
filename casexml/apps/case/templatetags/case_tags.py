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

import itertools

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

register = template.Library()

DYNAMIC_PROPERTIES_COLUMNS = 4

def build_tables(data, definition, processors=None, timezone=pytz.utc):
    processors = processors or {
        'utc_to_timezone': lambda d: utc_to_timezone(d, timezone=timezone),
        'yesno': yesno
    }

    
    layout = definition['layout']
    meta = definition['meta']

    def display_value(prop):
        val = data.pop(prop, None)

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


    #def set_colspan(rows):
        #if not rows:
            #return

        #max_row_length = max(map(len, rows))

        ## set colspan for last element in row if necessary
        #for row in rows:
            #if len(row) < max_row_length:
                #colspan = (max_row_length - len(row)) * 2 + 1
                #row.append([None, colspan, None])
   
    sections = []

    for section_name, rows in layout:
        processed_rows = [[[prop, _(name), display_value(prop)] 
                           for name, prop in row]
                          for row in rows]

        #set_colspan(processed_rows)
        columns = list(itertools.izip_longest(*processed_rows))
        sections.append((_(section_name) if section_name else "", columns))

    return sections

@register.simple_tag
def render_tables(tables, collapsible=False):
    return render_to_string("case/partials/property_table.html", {
        "tables": tables
    })

@register.simple_tag
def render_form(form):
    data = form.to_json()

    definition = {
        'layout': [
            (None, chunks(
                [(prop, prop) for prop in data.keys()],
                DYNAMIC_PROPERTIES_COLUMNS)
            )
        ],
        'meta': {
            '_date': {
                'process': 'utc_to_timezone'
            }
        }
    }

    tables = build_tables(data, definition=definition)

    return render_tables(tables)


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
                    ("Opened On", "opened_on"),
                    ("User ID", "user_id"),
                ],
                [
                    ("Modified On", "modified_on"),
                    ("Owner ID", "owner_id")
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
    
    data = case.to_json()
    default_properties = build_tables(
            data, definition=display, timezone=timezone)
    
    dynamic_data = dict((k, v) for (k, v) in case.dynamic_case_properties()
                        if k in data)
    definition = {
        'layout': [
            (None, chunks(
                [(prop, prop) for prop in dynamic_data.keys()],
                DYNAMIC_PROPERTIES_COLUMNS)
            )
        ],
        'meta': {
            '_date': {
                'process': 'utc_to_timezone'
            }
        }
    }

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
    
