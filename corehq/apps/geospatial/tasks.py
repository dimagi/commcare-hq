import math

from dimagi.utils.logging import notify_exception

from corehq.apps.celery import task
from corehq.apps.geospatial.const import (
    ES_INDEX_TASK_HELPER_BASE_KEY,
    DEFAULT_QUERY_LIMIT,
    DEFAULT_CHUNK_SIZE
)
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.apps.geospatial.utils import (
    get_celery_task_tracker,
    get_flag_assigned_cases_config,
    CeleryTaskTracker,
    update_cases_owner,
    get_geo_case_property,
)
from corehq.apps.geospatial.management.commands.index_utils import process_batch

from settings import MAX_GEOSPATIAL_INDEX_DOC_LIMIT


@task(queue="background_queue", ignore_result=True)
def geo_cases_reassignment_update_owners(domain, case_owner_updates_dict, task_key):
    try:
        flag_assigned_cases = get_flag_assigned_cases_config(domain)
        update_cases_owner(domain, case_owner_updates_dict, flag_assigned_cases)
    finally:
        celery_task_tracker = CeleryTaskTracker(task_key)
        celery_task_tracker.mark_completed()


@task(queue='geospatial_queue', ignore_result=True)
def index_es_docs_with_location_props(domain):
    celery_task_tracker = get_celery_task_tracker(domain, ES_INDEX_TASK_HELPER_BASE_KEY)
    geo_case_prop = get_geo_case_property(domain)
    query = case_query_for_missing_geopoint_val(domain, geo_case_prop)
    doc_count = query.count()
    if doc_count > MAX_GEOSPATIAL_INDEX_DOC_LIMIT:
        celery_task_tracker.mark_as_error(error_slug='TOO_MANY_CASES')
        return

    celery_task_tracker.mark_requested()
    batch_count = math.ceil(doc_count / DEFAULT_QUERY_LIMIT)
    try:
        for i in range(batch_count):
            docs_left = doc_count - (DEFAULT_QUERY_LIMIT * i)
            limit = min(DEFAULT_QUERY_LIMIT, docs_left)
            process_batch(
                domain,
                geo_case_prop,
                case_type=None,
                query_limit=limit,
                chunk_size=DEFAULT_CHUNK_SIZE,
                offset=i * DEFAULT_QUERY_LIMIT,
                total_count=doc_count
            )
            current_batch = i + 1
            celery_task_tracker.update_progress(
                current=current_batch * min(DEFAULT_CHUNK_SIZE, doc_count),
                total=doc_count
            )
    except Exception as e:
        celery_task_tracker.mark_as_error(error_slug='CELERY')
        notify_exception(
            None,
            'Something went wrong while indexing ES docs with location props.',
            details={
                'error': str(e),
                'domain': domain
            }
        )
    else:
        celery_task_tracker.mark_completed()
