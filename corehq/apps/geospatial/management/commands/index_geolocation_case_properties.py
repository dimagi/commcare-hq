import math

from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.es import case_search_adapter
from corehq.apps.es.client import manager
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.apps.geospatial.utils import get_geo_case_property
from corehq.form_processor.models import CommCareCase
from corehq.util.log import with_progress_bar

DEFAULT_QUERY_LIMIT = 10_000
DEFAULT_CHUNK_SIZE = 200


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
    query = case_query_for_missing_geopoint_val(domain, geo_case_property, case_type)
    count = query.count()
    print(f'{count} case(s) to process')
    batch_count = get_batch_count(count, query_limit)
    print(f"Cases will be processed in {batch_count} batches")
    for i in range(batch_count):
        print(f'Processing {i+1}/{batch_count}')
        process_batch(domain, geo_case_property, case_type, query_limit, chunk_size, with_progress=True)
    manager.index_refresh(case_search_adapter.index_name)


def get_batch_count(doc_count, query_limit):
    if not query_limit:
        return 1
    return math.ceil(doc_count / query_limit)


def process_batch(domain, geo_case_property, case_type, query_limit, chunk_size, with_progress=False, offset=0):
    query = case_query_for_missing_geopoint_val(
        domain, geo_case_property, case_type, size=query_limit, offset=offset
    )
    case_ids = query.get_ids()
    _index_case_ids(domain, case_ids, chunk_size, with_progress)


def _index_case_ids(domain, case_ids, chunk_size, with_progress=False):
    case_objects = CommCareCase.objects.get_cases(case_ids, domain)
    if with_progress:
        case_objs = with_progress_bar(case_objects)
    else:
        case_objs = case_objects
    for case_obj_chunk in chunked(case_objs, chunk_size):
        case_search_adapter.bulk_index(case_obj_chunk)
