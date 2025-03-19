import math

from django.core.management.base import BaseCommand

from corehq.apps.geospatial.const import DEFAULT_QUERY_LIMIT
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.apps.geospatial.management.commands.index_utils import process_batch
from corehq.apps.geospatial.utils import get_geo_case_property


class Command(BaseCommand):
    help = 'Index geopoint data in ES'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--case_type', required=False)

    def handle(self, *args, **options):
        domain = options['domain']
        case_type = options.get('case_type')
        index_case_docs(domain, case_type)


def index_case_docs(domain, case_type=None):
    geo_case_property = get_geo_case_property(domain)
    query = case_query_for_missing_geopoint_val(domain, geo_case_property, case_type)
    count = query.count()
    print(f'{count} case(s) to process')
    batch_count = math.ceil(count / DEFAULT_QUERY_LIMIT)
    print(f"Cases will be processed in {batch_count} batches")
    for i in range(batch_count):
        print(f'Processing {i+1}/{batch_count}')
        process_batch(
            domain,
            geo_case_property,
            total_count=count,
            case_type=case_type,
            with_progress=True,
            offset=i * DEFAULT_QUERY_LIMIT,
        )
