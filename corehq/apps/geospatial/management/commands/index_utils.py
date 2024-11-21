from dimagi.utils.chunked import chunked

from corehq.apps.es import case_search_adapter
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.form_processor.models import CommCareCase
from corehq.util.log import with_progress_bar


def process_batch(domain, geo_case_property, case_type, query_limit, chunk_size, with_progress=False, offset=0):
    query = case_query_for_missing_geopoint_val(
        domain, geo_case_property, case_type, size=query_limit, offset=offset
    )
    case_ids = query.get_ids()
    _index_case_ids(domain, case_ids, chunk_size, with_progress)


def _index_case_ids(domain, case_ids, chunk_size, with_progress):
    if with_progress:
        ids = with_progress_bar(case_ids)
    else:
        ids = case_ids
    for case_id_chunk in chunked(ids, chunk_size):
        case_chunk = CommCareCase.objects.get_cases(list(case_id_chunk), domain)
        case_search_adapter.bulk_index(case_chunk)
