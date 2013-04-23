from functools import partial
import copy
import datetime

from django.core.urlresolvers import reverse
from django import template
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import escape

import pytz
import simplejson

from corehq.apps.hqwebapp.templatetags.proptable_tags import (
    get_tables_as_columns, get_definition)

from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase


register = template.Library()

SYSTEM_FIELD_NAMES = (
    "drugs_prescribed", "case", "meta", "clinic_ids", "drug_drill_down", "tmp",
    "info_hack_done"
)

DYNAMIC_CASE_PROPERTIES_COLUMNS = 4


def sorted_case_update_keys(keys):
    """Put common @ attributes at the bottom"""
    def mycmp(x, y):
        if x[0] == '@' and y[0] == '@':
            return cmp(x, y)
        if x[0] == '@':
            return 1
        if y[0] == '@':
            return -1
        return cmp(x, y)
    return sorted(keys, cmp=mycmp)


def sorted_form_metadata_keys(keys):
    def mycmp(x, y):
        foo = ('timeStart', 'timeEnd')
        bar = ('username', 'userID')
        if x in foo and y in foo:
            return -1 if foo.index(x) == 0 else 1
        elif x in foo or y in foo:
            return 0

        if x in bar and y in bar:
            return -1 if bar.index(x) == 0 else 1
        elif x in bar and y in bar:
            return 0

        return cmp(x, y)
    return sorted(keys, cmp=mycmp)


def form_key_filter(key):
    if key in SYSTEM_FIELD_NAMES:
        return False

    if any(key.startswith(p) for p in ['#', '@', '_']):
        return False

    return True


@register.simple_tag
def render_form(form, domain, options):
    """
    Uses options since Django 1.3 doesn't seem to support templatetag kwargs.
    Change to kwargs when we're on a version of Django that does.
    
    """
    timezone = options.get('timezone', pytz.utc)
    #display = options.get('display')
    case_id = options.get('case_id')

    case_id_attr = "@%s" % const.CASE_TAG_ID

    _get_tables_as_columns = partial(get_tables_as_columns, timezone=timezone)

    # Form Data tab. deepcopy to ensure that if top_level_tags() returns live
    # references we don't change any data.
    form_dict = copy.deepcopy(form.top_level_tags())
    form_dict.pop('change', None)  # this data already in Case Changes tab
    form_keys = [k for k in form_dict.keys() if form_key_filter(k)]
    form_data = _get_tables_as_columns(form_dict, get_definition(form_keys))

    # Case Changes tab
    case_blocks = extract_case_blocks(form)
    for i, block in enumerate(list(case_blocks)):
        if case_id and block.get(case_id_attr) == case_id:
            case_blocks.pop(i)
            case_blocks.insert(0, block)

    cases = []
    for b in case_blocks:
        this_case_id = b.get(case_id_attr)
        this_case = CommCareCase.get(this_case_id) if this_case_id else None

        if this_case and this_case._id:
            url = reverse('case_details', args=[domain, this_case._id])
        else:
            url = "#"

        definition = get_definition(sorted_case_update_keys(b.keys()))
        cases.append({
            "is_current_case": case_id and this_case_id == case_id,
            "name": case_inline_display(this_case),
            "table": _get_tables_as_columns(b, definition),
            "url": url
        })

    # Form Metadata tab
    meta = form_dict.pop('meta')
    definition = get_definition(sorted_form_metadata_keys(meta.keys()))
    form_meta_data = _get_tables_as_columns(meta, definition)

    return render_to_string("case/partials/single_form.html", {
        "context_case_id": case_id,
        "instance": form,
        "is_archived": form.doc_type == "XFormArchived",
        "domain": domain,
        "form_data": form_data,
        "cases": cases,
        "form_table_options": {
            # todo: wells if display config has more than one column
            "put_loners_in_wells": False
        },
        "form_meta_data": form_meta_data,
    })


@register.simple_tag
def render_case(case, options):
    """
    Uses options since Django 1.3 doesn't seem to support templatetag kwargs.
    Change to kwargs when we're on a version of Django that does.
    
    """
    timezone = options.get('timezone', pytz.utc)
    _get_tables_as_columns = partial(get_tables_as_columns, timezone=timezone)
    display = options.get('display', None)

    display = display or [
        {
            "layout": [
                [
                    {
                        "expr": "name",
                        "name": _("Name"),
                    },
                    {
                        "expr": "opened_on",
                        "name": _("Opened On"),
                        "parse_date": True,
                    },
                    {
                        "expr": "modified_on",
                        "name": _("Modified On"),
                        "parse_date": True,
                    },
                    {
                        "expr": "closed_on",
                        "name": _("Closed On"),
                        "parse_date": True,
                    },
                ],
                [
                    {
                        "expr": "type",
                        "name": _("Case Type"),
                        "format": '<code>{0}</code>',
                    },
                    {
                        "expr": "user_id",
                        "name": _("User ID"),
                        "format": '<span data-field="user_id">{0}</span>',
                    },
                    {
                        "expr": "owner_id",
                        "name": _("Owner ID"),
                        "format": '<span data-field="owner_id">{0}</span>',
                    },
                    {
                        "expr": "_id",
                        "name": _("Case ID"),
                    },
                ],
            ],
        }
    ]

    data = copy.deepcopy(case.to_json())

    default_properties = _get_tables_as_columns(data, display)

    # pop seen properties off of remaining case properties
    dynamic_data = dict(case.dynamic_case_properties())
    for section in display:
        for row in section['layout']:
            for item in row:
                dynamic_data.pop(item.get("expr"), None)

    dynamic_keys = sorted(dynamic_data.keys())
    definition = get_definition(
            dynamic_keys, num_columns=DYNAMIC_CASE_PROPERTIES_COLUMNS)

    dynamic_properties = _get_tables_as_columns(dynamic_data, definition)

    actions = case.to_json()['actions']
    actions.reverse()

    tz_abbrev = timezone.localize(datetime.datetime.now()).tzname()

    return render_to_string("case/partials/single_case.html", {
        "default_properties": default_properties,
        "default_properties_options": {
            "style": "table"
        },
        "dynamic_properties": dynamic_properties,
        "dynamic_properties_options": {
            "style": "table"
        },
        "case": case,
        "case_actions": mark_safe(simplejson.dumps(actions)),
        "timezone": timezone,
        "tz_abbrev": tz_abbrev
    })
    
    
@register.simple_tag
def case_inline_display(case):
    """
    Given a case id, make a best effort at displaying it.
    """
    if case:
        if case.opened_on:
            ret = "%s (%s: %s)" % (case.name, _("Opened"), case.opened_on.date())
        else:
            ret =  case.name
    else:
        ret = _("Empty Case")

    return escape(ret)
    
