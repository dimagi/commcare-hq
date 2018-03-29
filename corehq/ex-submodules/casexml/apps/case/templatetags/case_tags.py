from __future__ import absolute_import
from __future__ import unicode_literals
from functools import partial
import copy
import datetime
import numbers
import pytz
import json
import types

from django import template
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.html import escape

from corehq.apps.products.models import SQLProduct
from corehq.motech.repeaters.dbaccessors import get_repeat_records_by_payload_id
from couchdbkit import ResourceNotFound
from corehq.apps.users.util import cached_owner_id_to_display

from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors

from casexml.apps.case.views import get_wrapped_case

register = template.Library()


def normalize_date(val):
    # Can't use isinstance since datetime is a subclass of date.
    if type(val) == datetime.date:
        return datetime.datetime.combine(val, datetime.time.min)

    return val


def get_inverse(val):
    if isinstance(val, (datetime.datetime, datetime.date)):
        return datetime.datetime.max - val
    elif isinstance(val, numbers.Number):
        return 10 ** 20
    elif val is None or isinstance(val, bool):
        return not val
    else:
        raise Exception("%r has uninversable type: %s" % (val, type(val)))


def sortkey(child, type_info=None):
    """Return sortkey based on sort order defined in type_info, or use default
    based on open/closed and opened_on/closed_on dates.
    """
    type_info = type_info or {}
    case = child['case']
    if case.closed:
        key = [1]
        try:
            for attr, direction in type_info[case.type]['closed_sortkeys']:
                val = normalize_date(getattr(case, attr))
                if direction.lower() == 'desc':
                    val = get_inverse(val)
                key.append(val)
        except KeyError:
            key.append(datetime.datetime.max - case.closed_on)
    else:
        key = [0]
        try:
            for attr, direction in type_info[case.type]['open_sortkeys']:
                val = normalize_date(getattr(case, attr))
                if direction.lower() == 'desc':
                    val = get_inverse(val)
                key.append(val)
        except KeyError:
            key.append(case.opened_on or datetime.datetime.min)
    return key


def get_session_data(case, current_case, type_info):
    # this logic should ideally be implemented in subclasses of
    # CommCareCase
    if type_info and case.type in type_info:
        attr = type_info[case.type]['case_id_attr']
        return {
            attr: case.case_id,
            'case_id': current_case.case_id
        }
    else:
        return {
            'case_id': case.case_id
        }


TREETABLE_INDENT_PX = 19


def process_case_hierarchy(case_output, get_case_url, type_info):
    current_case = case_output['case']
    submit_url_root = reverse('receiver_post', args=[current_case.domain])
    form_url_root = reverse('formplayer_main', args=[current_case.domain])

    def process_output(case_output, depth=0):
        for c in case_output['child_cases']:
            process_output(c, depth=depth + 1)

        case = case_output['case']
        common_data = {
            'indent_px': depth * TREETABLE_INDENT_PX,
            'submit_url_root': submit_url_root,
            'form_url_root': form_url_root,
            'view_url': get_case_url(case.case_id),
            'session_data': get_session_data(case, current_case, type_info)
        }
        data = type_info.get(case.type, {})
        if 'description_property' in data:
            data['description'] = getattr(
                    case, data['description_property'], None)
        if 'edit_session_data' in data:
            data['session_data'].update(data['edit_session_data'])
        data.update(common_data)

        case.edit_data = data

        if 'child_type' in data and not case.closed:
            child_type = data['child_type']
            child_data = type_info.get(child_type, {})
            child_data.update(common_data)
            child_data.update({
                "link_text": _("Add %(case_type)s") % {
                    'case_type': child_data.get('type_name', child_type)
                },
                "parent_node_id": case.case_id,
            })

            if 'create_session_data' in child_data:
                child_data['session_data'].update(child_data['create_session_data'])
            case.add_child_data = child_data

    process_output(case_output)


def get_case_hierarchy(case, type_info):
    def get_children(case, referenced_type=None, seen=None):
        seen = seen or set()

        ignore_types = type_info.get(case.type, {}).get("ignore_relationship_types", [])
        if referenced_type and referenced_type in ignore_types:
            return None

        seen.add(case.case_id)
        children = [
            get_children(i.referenced_case, i.referenced_type, seen) for i in case.reverse_indices
            if i.referenced_id not in seen
        ]

        children = [c for c in children if c is not None]

        # non-first-level descendants
        descendant_types = []
        for c in children:
            descendant_types.extend(c['descendant_types'])
        descendant_types = list(set(descendant_types))

        children = sorted(children, key=partial(sortkey, type_info=type_info))
       
        # set parent_case_id used by flat display
        for c in children:
            if not hasattr(c['case'], 'treetable_parent_node_id'):
                c['case'].treetable_parent_node_id = case.case_id
      
        child_cases = []
        for c in children:
            child_cases.extend(c['case_list'])

        return {
            'case': case,
            'child_cases': children,
            'descendant_types': list(set(descendant_types + [c['case'].type for c in children])),
            'case_list': [case] + child_cases
        }

    return get_children(case)


def get_flat_descendant_case_list(case, get_case_url, type_info=None):
    type_info = type_info or {}
    hierarchy = get_case_hierarchy(case, type_info)
    process_case_hierarchy(hierarchy, get_case_url, type_info)
    return hierarchy['case_list']


@register.simple_tag
def render_case_hierarchy(case, options):
    from corehq.apps.hqwebapp.templatetags.proptable_tags import get_display_data

    wrapped_case = get_wrapped_case(case)
    get_case_url = options.get('get_case_url')
    timezone = options.get('timezone', pytz.utc)
    columns = options.get('columns') or wrapped_case.related_cases_columns
    show_view_buttons = options.get('show_view_buttons', True)
    type_info = options.get('related_type_info', wrapped_case.related_type_info)

    descendent_case_list = get_flat_descendant_case_list(
        case, get_case_url, type_info=type_info
    )

    parent_cases = []
    if case.indices:
        # has parent case(s)
        # todo: handle duplicates in ancestor path (bubbling up of parent-child
        # relationships)
        for idx in case.indices:
            try:
                parent_cases.append(idx.referenced_case)
            except ResourceNotFound:
                parent_cases.append(None)
        for parent_case in parent_cases:
            if parent_case:
                parent_case.edit_data = {
                    'view_url': get_case_url(parent_case.case_id)
                }
                last_parent_id = parent_case.case_id
            else:
                last_parent_id = None

        for c in descendent_case_list:
            if not getattr(c, 'treetable_parent_node_id', None) and last_parent_id:
                c.treetable_parent_node_id = last_parent_id

    case_list = parent_cases + descendent_case_list

    for c in case_list:
        if not c:
            continue
        c.columns = []
        case_dict = get_wrapped_case(c).to_full_dict()
        for column in columns:
            c.columns.append(get_display_data(
                case_dict, column, timezone=timezone))

    return render_to_string("case/partials/case_hierarchy.html", {
        'current_case': case,
        'domain': case.domain,
        'case_list': case_list,
        'columns': columns,
        'num_columns': len(columns) + 1,
        'show_view_buttons': show_view_buttons,
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
            ret = case.name
    else:
        ret = _("Empty Case")

    return escape(ret)
