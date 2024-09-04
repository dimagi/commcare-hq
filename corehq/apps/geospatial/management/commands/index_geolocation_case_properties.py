from django.core.management.base import BaseCommand
from corehq.apps.es import CaseSearchES, filters, queries
from corehq.apps.es.case_search import (
    CASE_PROPERTIES_PATH,
    PROPERTY_GEOPOINT_VALUE,
    PROPERTY_KEY,
)


class Command(BaseCommand):
    help = 'Index geopoint data in ES'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--case_type', required=False)
        parser.add_argument('--query_limit', required=False)
        parser.add_argument('--chunk_size', required=False)

    def handle(self, *args, **options):
        domain = options['domain']
        case_type = options.get('case_type')
        query_limit = options.get('query_limit')
        chunk_size = options.get('chunk_size')


def _case_query(domain, geo_case_property, case_type=None, size=None):
    query = (
        CaseSearchES()
        .domain(domain)
        .filter(_geopoint_value_missing_for_property(geo_case_property))
    )
    if case_type:
        query = query.case_type(case_type)
    if size:
        query = query.size(size)
    return query


def _geopoint_value_missing_for_property(geo_case_property_name):
    """
    Query to find docs with missing 'geopoint_value' for the given case property.
    """
    return queries.nested(
        CASE_PROPERTIES_PATH,
        queries.filtered(
            queries.match_all(),
            filters.AND(
                filters.term(PROPERTY_KEY, geo_case_property_name),
                filters.missing(PROPERTY_GEOPOINT_VALUE)
            )
        )
    )
