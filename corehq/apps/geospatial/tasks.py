from corehq.util.decorators import serial_task

from corehq.apps.celery import task
from corehq.apps.geospatial.const import INDEX_ES_TASK_HELPER_BASE_KEY
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.apps.geospatial.utils import (
    get_celery_task_tracker,
    get_flag_assigned_cases_config,
    CeleryTaskTracker,
    update_cases_owner,
    get_geo_case_property,
)
from corehq.apps.geospatial.management.commands.index_geolocation_case_properties import (
    get_batch_count,
    process_batch,
    DEFAULT_QUERY_LIMIT,
    DEFAULT_CHUNK_SIZE,
)

from settings import MAX_GEOSPATIAL_INDEX_DOC_LIMIT


@task(queue="background_queue", ignore_result=True)
def geo_cases_reassignment_update_owners(domain, case_owner_updates_dict, task_key):
    try:
        flag_assigned_cases = get_flag_assigned_cases_config(domain)
        update_cases_owner(domain, case_owner_updates_dict, flag_assigned_cases)
    finally:
        celery_task_tracker = CeleryTaskTracker(task_key)
        celery_task_tracker.mark_completed()


@serial_task('async-index-es-docs', timeout=60 * 60, queue='background_queue', ignore_result=True)
def index_es_docs_with_location_props(domain):
    celery_task_tracker = get_celery_task_tracker(domain, INDEX_ES_TASK_HELPER_BASE_KEY)
    if celery_task_tracker.is_active():
        return

    geo_case_prop = get_geo_case_property(domain)
    query = case_query_for_missing_geopoint_val(domain, geo_case_prop)
    doc_count = query.count()
    if doc_count > MAX_GEOSPATIAL_INDEX_DOC_LIMIT:
        celery_task_tracker.mark_as_error(error_slug='TOO_MANY_CASES')
        return

    celery_task_tracker.mark_requested()
    batch_count = get_batch_count(doc_count, DEFAULT_QUERY_LIMIT)
    try:
        for i in range(batch_count):
            process_batch(
                domain,
                geo_case_prop,
                case_type=None,
                query_limit=DEFAULT_QUERY_LIMIT,
                chunk_size=DEFAULT_CHUNK_SIZE,
            )
            celery_task_tracker.update_progress(current=i + 1, total=batch_count)
    except Exception:
        celery_task_tracker.mark_as_error(error_slug='CELERY')
    else:
        celery_task_tracker.mark_completed()
