import copy
from django import template
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.core.urlresolvers import reverse

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
from casexml.apps.case.models import CommCareCase

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

register = template.Library()

DYNAMIC_CASE_PROPERTIES_COLUMNS = 4
FORM_PROPERTIES_COLUMNS = 1

def is_list(val):
    return (isinstance(val, collections.Iterable) and 
            not isinstance(val, basestring))

def get_display(key, val, dt_format="%b %d, %Y %H:%M %Z", timezone=pytz.utc,
                parse_dates=True, key_format=None, level=0,
                collapse_lists=False):

    recurse = lambda k, v: get_display(k, v,
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


def build_table_rows(data, definition, processors=None, timezone=pytz.utc):
    default_processors = {
        'yesno': yesno
    }
    processors = processors or {}
    processors.update(default_processors)

    def get_value(data, expr):
        # todo: nested attributes, support for both getitem and getattr

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
                if not val:
                    val = '---'

        if isinstance(val, datetime.datetime):
            if val.tzinfo is None:
                val = val.replace(tzinfo=pytz.utc)

            val = adjust_datetime_to_timezone(val, val.tzinfo, timezone.zone)


        if process:
            val = escape(processors[process](val))
        else:
            val = mark_safe(get_display(None,
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

        sections.append({
            "name": section.get('name') or '',
            "rows": rows
        })

    return sections

def build_table_columns(*args, **kwargs):
    sections = build_table_rows(*args, **kwargs)
    for section in sections:
        section['columns'] = list(itertools.izip_longest(*section['rows']))

    return sections
    

@register.simple_tag
def render_tables(tables, options=None):
    options = options or {}
    id = options.get('id')
    adjust_heights = options.get('adjust_heights', True)
    put_loners_in_wells = options.get('put_loners_in_wells', True)

    if id is None:
        import uuid
        id = "a" + str(uuid.uuid4())

    return render_to_string("case/partials/dl_property_table.html", {
        "tables": tables,
        "id": id,
        "adjust_heights": adjust_heights,
        "put_loners_in_wells": put_loners_in_wells
    })


def get_definition(keys, num_columns=FORM_PROPERTIES_COLUMNS, name=None):
    layout = chunks([{"expr": prop} for prop in keys], num_columns)

    return [
        {
            "name": name,
            "layout": layout
        }
    ]


def sorted_case_update_keys(keys):
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

    # Form Data tab. deepcopy to ensure that if top_level_tags() returns live
    # references we don't change any data.
    form_dict = copy.deepcopy(form.top_level_tags())
    form_dict.pop('change', None)  # this data already in Case Changes tab
    form_keys = [k for k in form_dict.keys() if form_key_filter(k)]
    form_data = build_table_columns(
            form_dict, definition=get_definition(form_keys), timezone=timezone)

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

        cases.append({
            "is_current_case": case_id and this_case_id == case_id,
            "name": case_inline_display(this_case),
            "table": build_table_columns(
                b, definition=get_definition(
                    sorted_case_update_keys(b.keys())),
                timezone=timezone),
            "url": url
        })

    # Form Metadata tab
    meta = form_dict.pop('meta')
    form_meta_data = build_table_columns(
            meta, definition=get_definition(
                sorted_form_metadata_keys(meta.keys())),
            timezone=timezone)

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
    
    default_properties = build_table_columns(
            data, definition=display, timezone=timezone)

    # pop seen properties off of remaining case properties
    dynamic_data = dict(case.dynamic_case_properties())
    for section in display:
        for row in section['layout']:
            for item in row:
                dynamic_data.pop(item.get("expr"), None)


    dynamic_keys = sorted(dynamic_data.keys())
    definition = [
        {
            "layout": chunks(
                [{"expr": prop} for prop in dynamic_keys],
                DYNAMIC_CASE_PROPERTIES_COLUMNS)
        }
    ]

    dynamic_properties = build_table_columns(
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
            ret = "%s (%s: %s)" % (case.name, _("Opened"), case.opened_on.date())
        else:
            ret =  case.name
    else:
        ret = _("Empty Case")

    return escape(ret)
    
