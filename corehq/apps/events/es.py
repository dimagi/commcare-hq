from __future__ import annotations

from corehq.apps.es import CaseES
from corehq.apps.events.models import get_attendee_case_type
from corehq.form_processor.models import CommCareCase


def get_paginated_attendees(domain, limit, page, query=None):
    case_type = get_attendee_case_type(domain)
    if query:
        es_query = (
            CaseES()
            .domain(domain)
            .case_type(case_type)
            .is_closed(False)
            .search_string_query(query, ['name'])
        )
        total = es_query.count()
        case_ids = es_query.get_ids()
    else:
        case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(
            domain,
            case_type,
        )
        total = len(case_ids)
    if page:
        start, end = page_to_slice(limit, page)
        cases = CommCareCase.objects.get_cases(case_ids[start:end], domain)
    else:
        cases = CommCareCase.objects.get_cases(case_ids[:limit], domain)
    return cases, total


def page_to_slice(limit, page):
    """
    Converts ``limit``, ``page`` to start and end indices.

    Assumes page numbering starts at 1.

    >>> names = ['Harry', 'Hermione', 'Ron']
    >>> start, end = page_to_slice(limit=1, page=2)
    >>> names[start:end]
    ['Hermione']
    """
    assert page > 0, 'Page numbering starts at 1'

    start = (page - 1) * limit
    end = start + limit
    return start, end
