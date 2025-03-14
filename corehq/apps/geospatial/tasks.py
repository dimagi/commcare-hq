import math
import time

from corehq.apps.geospatial.models import GeoConfig
from corehq.apps.geospatial.routing_solvers.pulp import RoadNetworkSolver
from dimagi.utils.logging import notify_exception

from corehq.apps.celery import task
from corehq.apps.geospatial.const import (
    ES_INDEX_TASK_HELPER_BASE_KEY,
    ES_REASSIGNMENT_UPDATE_OWNERS_BASE_KEY,
    DEFAULT_QUERY_LIMIT,
)
from corehq.apps.geospatial.es import case_query_for_missing_geopoint_val
from corehq.apps.geospatial.utils import (
    get_celery_task_tracker,
    get_flag_assigned_cases_config,
    update_cases_owner,
    get_geo_case_property,
)
from corehq.apps.geospatial.management.commands.index_utils import process_batch

from settings import MAX_GEOSPATIAL_INDEX_DOC_LIMIT


@task(queue="background_queue", ignore_result=True)
def geo_cases_reassignment_update_owners(domain, case_owner_updates_dict):
    celery_task_tracker = get_celery_task_tracker(domain, ES_REASSIGNMENT_UPDATE_OWNERS_BASE_KEY)
    try:
        flag_assigned_cases = get_flag_assigned_cases_config(domain)
        update_cases_owner(domain, case_owner_updates_dict, flag_assigned_cases, celery_task_tracker)
    except Exception as e:
        notify_exception(
            None,
            'Something went wrong while reassigning cases to mobile workers.',
            details={
                'error': str(e),
                'domain': domain
            }
        )
    finally:
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
            process_batch(
                domain,
                geo_case_prop,
                offset=i * DEFAULT_QUERY_LIMIT,
                total_count=doc_count
            )
            current_batch = i + 1
            processed_count = min(current_batch * DEFAULT_QUERY_LIMIT, doc_count)
            celery_task_tracker.update_progress(
                current=processed_count,
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


@task(queue='geospatial_queue', ignore_result=True)
def clusters_disbursement_task(domain, clusters):
    config = GeoConfig.objects.get(domain=domain)

    print(f"Processing disbursement for {len(clusters)} clusters ...")
    start_time = time.time()
    assignments = []
    for cluster_id in clusters.keys():
        users_chunk = clusters[cluster_id]['users']
        cases_chunk = clusters[cluster_id]['cases']
        if users_chunk and cases_chunk:
            print(f"Starting disbursement for cluster: {cluster_id}, total users: {len(users_chunk)},"
                  f" total cases: {len(cases_chunk)}")
            try:
                solver = RoadNetworkSolver(clusters[cluster_id])
                result = solver.solve(config)
                assignments.append(result)
            except Exception as e:
                print(f"Error occurred for disbursement for cluster: {cluster_id} : {str(e)}")
                continue
            print(f"Completed disbursement for cluster: {cluster_id}")
        elif users_chunk:
            print(f"No cases available for mobile workers in cluster: {cluster_id}")
        elif cases_chunk:
            print(f"No mobile workers available for cases in cluster: {cluster_id}")
    print(f"Total Time for solving disbursements: {time.time() - start_time}")
    return assignments
