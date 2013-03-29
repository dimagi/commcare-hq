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

register = template.Library()

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
                    ("Modified On", "modified_on"),
                    ("Closed On", "closed_on"),
                ],
                [
                    ("User ID", "user_id"),
                    ("Owner ID", "owner_id")
                ]
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
    
    processed_layout = []

    for section_name, rows in layout:
        processed_rows = []

        for row in rows:
            processed_row = []

            for name, attr in row:
                val = getattr(case, attr, None)

                if attr in meta:
                    attr_meta = meta[attr]
                elif isinstance(val, datetime.datetime):
                    attr_meta = meta['_date']
                else:
                    attr_meta = {}

                if 'process' in attr_meta:
                    val = processors[attr_meta['process']](val)
                val = escape(val)

                if 'format' in attr_meta:
                    val = mark_safe(attr_meta['format'].format(val))
                
                processed_row.append((attr, _(name), val))

            processed_rows.append(processed_row)

        columns = list(itertools.izip_longest(*processed_rows))
        span = len(columns) * 2
        processed_layout.append((_(section_name), span, columns))
    
    return render_to_string("case/partials/single_case.html", {
        "layout": processed_layout,
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
    
