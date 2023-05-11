from __future__ import annotations

from django.core.paginator import Paginator

from corehq.apps.es import CaseES, CaseSearchES
from corehq.apps.es.case_search import case_property_text_query
from corehq.apps.events.models import (
    LOCATION_IDS_CASE_PROPERTY,
    get_attendee_case_type,
)
from corehq.form_processor.models import CommCareCase


class AttendeeSearchES(CaseSearchES):
    """
    Allows Attendee cases to be searched by location, like Users.
    """
    @property
    def builtin_filters(self):
        return [
            attendee_location_filter,
        ] + super().builtin_filters


def attendee_location_filter(location_ids):
    """
    Return Attendee cases whose location IDs include at least one of
    ``location_ids``.
    """
    if not isinstance(location_ids, str):
        location_ids = ' '.join(location_ids)
    return case_property_text_query(
        LOCATION_IDS_CASE_PROPERTY,
        location_ids,
        operator='or',  # Any location ID will be a hit
    )


def get_paginated_attendees(domain, limit, page, query=None):
    assert page > 0, 'Page numbering starts at 1'
    assert limit > 0, f'{limit} is not a valid limit'

    case_type = get_attendee_case_type(domain)
    if query:
        es_query = (
            CaseES()
            .domain(domain)
            .case_type(case_type)
            .is_closed(False)
            .search_string_query(query, ['name'])
        )
        case_ids = es_query.get_ids()
    else:
        case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(
            domain,
            case_type,
        )
    paginator = Paginator(case_ids, limit)
    case_ids_page = list(paginator.get_page(page))
    cases = CommCareCase.objects.get_cases(case_ids_page, domain)
    return cases, paginator.count
