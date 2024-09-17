import math

from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.es import CaseSearchES, case_search_adapter, filters, queries
from corehq.apps.es.case_search import (
    CASE_PROPERTIES_PATH,
    PROPERTY_GEOPOINT_VALUE,
    PROPERTY_KEY,
)
from corehq.apps.es.client import manager
from corehq.apps.geospatial.utils import get_geo_case_property
from corehq.form_processor.models import CommCareCase
from corehq.util.log import with_progress_bar

DEFAULT_QUERY_LIMIT = 10_000
DEFAULT_CHUNK_SIZE = 100


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
        index_case_docs(domain, query_limit, chunk_size, case_type)


def index_case_docs(domain, query_limit=DEFAULT_QUERY_LIMIT, chunk_size=DEFAULT_CHUNK_SIZE, case_type=None):
    geo_case_property = get_geo_case_property(domain)
    query = _es_case_query(domain, geo_case_property, case_type)
    count = query.count()
    print(f'{count} case(s) to process')
    batch_count = get_batch_count(count, query_limit)
    print(f"Cases will be processed in {batch_count} batches")
    for i in range(batch_count):
        print(f'Processing {i+1}/{batch_count}')
        process_batch(domain, geo_case_property, case_type, query_limit, chunk_size)


def get_batch_count(doc_count, query_limit):
    if not query_limit:
        return 1
    return math.ceil(doc_count / query_limit)


def process_batch(domain, geo_case_property, case_type, query_limit, chunk_size):
    query = _es_case_query(domain, geo_case_property, case_type, size=query_limit)
    case_ids = query.get_ids()
    _index_case_ids(domain, case_ids, chunk_size)


def _index_case_ids(domain, case_ids, chunk_size):
    for case_id_chunk in chunked(with_progress_bar(case_ids), chunk_size):
        case_chunk = CommCareCase.objects.get_cases(list(case_id_chunk), domain)
        case_search_adapter.bulk_index(case_chunk)
    manager.index_refresh(case_search_adapter.index_name)


def _es_case_query(domain, geo_case_property, case_type=None, size=None):
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
