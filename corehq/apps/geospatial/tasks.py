from corehq.apps.celery import task
from corehq.apps.geospatial.utils import update_cases_owner


@task(queue="background_queue")
def geo_cases_reassignment_update_owners(domain, case_id_to_owner_id):
    update_cases_owner(domain, case_id_to_owner_id)
