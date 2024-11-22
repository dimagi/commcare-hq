import math

from django.core.management.base import BaseCommand

from corehq.apps.geospatial.const import DEFAULT_QUERY_LIMIT, DEFAULT_CHUNK_SIZE
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.apps.geospatial.management.commands.index_utils import process_batch
from corehq.apps.geospatial.utils import get_geo_case_property


class Command(BaseCommand):
    help = 'Index geopoint data in ES'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--case_type', required=False)
        parser.add_argument('--query_limit', type=int, required=False, default=DEFAULT_QUERY_LIMIT)
        parser.add_argument('--chunk_size', required=False)

    def handle(self, *args, **options):
        domain = options['domain']
        case_type = options.get('case_type')
        query_limit = options.get('query_limit')
        chunk_size = options.get('chunk_size')
        index_case_docs(domain, query_limit, chunk_size, case_type)


def index_case_docs(domain, query_limit=DEFAULT_QUERY_LIMIT, chunk_size=DEFAULT_CHUNK_SIZE, case_type=None):
    assert query_limit > 0, "query_limit should be a positive number greater than 0"

    geo_case_property = get_geo_case_property(domain)
    query = case_query_for_missing_geopoint_val(domain, geo_case_property, case_type)
    count = query.count()
    print(f'{count} case(s) to process')
    batch_count = math.ceil(count / query_limit)
    print(f"Cases will be processed in {batch_count} batches")
    for i in range(batch_count):
        print(f'Processing {i+1}/{batch_count}')
        process_batch(
            domain,
            geo_case_property,
            case_type,
            query_limit,
            chunk_size,
            with_progress=True,
            total_count=count
        )
