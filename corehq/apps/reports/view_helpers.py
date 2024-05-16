import datetime
import numbers
from django.urls import reverse
from django.utils.translation import gettext as _

import pytz
from couchdbkit import ResourceNotFound

from casexml.apps.case.views import get_wrapped_case

from corehq.apps.hqwebapp.templatetags.proptable_tags import get_display_data


def case_hierarchy_context(case, get_case_url, timezone=None):
    wrapped_case = get_wrapped_case(case)
    if timezone is None:
        timezone = pytz.utc
    columns = wrapped_case.related_cases_columns
    descendant_case_list = _get_flat_descendant_case_list(case, get_case_url)

    parent_cases = []
    if case.live_indices:
        # has parent case(s)
        # todo: handle duplicates in ancestor path (bubbling up of parent-child
        # relationships)
        for idx in case.live_indices:
            try:
                parent_case = idx.referenced_case
                parent_case.index_info = _index_to_context(idx, is_ancestor=True)
                parent_cases.append(parent_case)
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

        for c in descendant_case_list:
            if not getattr(c, 'treetable_parent_node_id', None) and last_parent_id:
                c.treetable_parent_node_id = last_parent_id

    reverse_indices = {index.case_id: index for index in case.reverse_indices}
    for descendant in descendant_case_list:
        if idx := reverse_indices.get(descendant.case_id):
            descendant.index_info = _index_to_context(idx, is_ancestor=False)

    case_list = parent_cases + descendant_case_list

    for c in case_list:
        if not c:
            continue
        c.columns = []
        case_dict = get_wrapped_case(c).to_full_dict()
        for column in columns:
            c.columns.append(get_display_data(
                case_dict, column, timezone=timezone))

    return {
        'current_case': case,
        'domain': case.domain,
        'case_list': case_list,
        'columns': columns,
    }


def _index_to_context(index, is_ancestor):
    return {
        'identifier': index.identifier,
        'relationship': index.relationship,
        'is_ancestor': is_ancestor,
    }


def _sortkey(child):
    """Return sortkey based on open/closed and opened_on/closed_on dates"""
    case = child['case']
    if case.closed:
        return (1, datetime.datetime.max - case.closed_on)
    return (0, case.opened_on or datetime.datetime.min)


def _process_case_hierarchy(case_output, get_case_url):
    def process_output(case_output, depth=0):
        for c in case_output['child_cases']:
            process_output(c, depth=depth + 1)

        case = case_output['case']
        case.edit_data = {
            'view_url': get_case_url(case.case_id),
        }
    process_output(case_output)


def get_case_hierarchy(case):
    def get_children(case, seen):
        seen.add(case.case_id)
        children = [
            get_children(i.referenced_case, seen) for i in case.reverse_indices
            if i.referenced_id and i.referenced_id not in seen
        ]
        children = sorted(children, key=_sortkey)

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
            'case_list': [case] + child_cases
        }

    return get_children(case, seen=set())


def _get_flat_descendant_case_list(case, get_case_url):
    hierarchy = get_case_hierarchy(case)
    _process_case_hierarchy(hierarchy, get_case_url)
    return hierarchy['case_list']
