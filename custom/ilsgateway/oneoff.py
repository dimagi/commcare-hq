import celery
from datetime import datetime, timedelta

import itertools

from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import OneOffTaskProgress
from custom.ilsgateway.tanzania.warehouse.updater import process_non_facility_warehouse_data, default_start_date


@celery.task(ignore_result=True, queue='logistics_background_queue')
def recalculate_moshi_rural_task():
    site_code = 'district-moshi-rural'
    moshi = SQLLocation.objects.get(domain='ils-gateway', site_code__iexact=site_code)
    end_date = datetime(2016, 3, 1) - timedelta(microseconds=.1)

    process_non_facility_warehouse_data(moshi, default_start_date(), end_date, strict=False)

TASK_NAME = '2016-04-12_recalculate_non_facilities_task'


@celery.task(ignore_result=True, queue='logistics_background_queue')
def recalculate_non_facilities_task(domain):
    task_progress = OneOffTaskProgress.objects.get_or_create(domain=domain, task_name=TASK_NAME)[0]
    if task_progress.complete:
        return

    start_date = default_start_date()
    end_date = datetime(2016, 3, 1) - timedelta(microseconds=.1)

    districts = list(SQLLocation.active_objects.filter(
        domain='ils-gateway', location_type__name__iexact='DISTRICT'
    ).order_by('pk'))
    regions = list(SQLLocation.active_objects.filter(
        domain='ils-gateway', location_type__name__iexact='REGION'
    ).order_by('pk'))
    msd_zones = list(SQLLocation.active_objects.filter(
        domain='ils-gateway', location_type__name__iexact='MSDZONE'
    ).order_by('pk'))
    mohsw = list(SQLLocation.active_objects.filter(
        domain='ils-gateway', location_type__name__iexact='MOHSW'
    ).order_by('pk'))

    non_facilities = districts + regions + msd_zones + mohsw
    task_progress.total = len(non_facilities)
    task_progress.save()

    if task_progress.last_synced_object_id:
        non_facilities = list(itertools.dropwhile(
            lambda x: x.location_id != task_progress.last_synced_object_id,
            non_facilities
        ))
        last_processed = non_facilities[0]
        non_facilities = non_facilities[1:]
        process_non_facility_warehouse_data(last_processed, start_date, end_date, strict=False)

    for non_facility in non_facilities:
        task_progress.last_synced_object_id = non_facility.location_id
        task_progress.progress += 1
        task_progress.save()
        process_non_facility_warehouse_data(
            non_facility, default_start_date(), end_date, strict=False
        )

    task_progress.complete = True
    task_progress.save()
