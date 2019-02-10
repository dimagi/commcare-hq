from __future__ import absolute_import, unicode_literals

from datetime import datetime

from celery.task import task
from django.db import connections

from custom.aaa.models import AggregationInformation, Child


def update_table(domain, slug, method):
    window_start = AggregationInformation.objects.filter(
        step=slug, aggregation_window_end__isnull=False
    ).order_by('-created_at').values_list('aggregation_window_end').first()
    if window_start is None:
        window_start = datetime(1900, 1, 1)
    else:
        window_start = window_start[0]

    window_end = datetime.utcnow()
    agg_info = AggregationInformation.objects.create(
        domain=domain,
        step=slug,
        aggregation_window_start=window_start,
        aggregation_window_end=window_end,
    )

    # implement lock

    agg_query, agg_params = method(domain, window_start, window_end)
    with connections['aaa-data'].cursor() as cursor:
        cursor.execute(agg_query, agg_params)
    agg_info.end_time = datetime.utcnow()
    agg_info.save()


@task
def update_base_child_table(domain):
    update_table(domain, 'Child.agg_from_child_health_case_ucr', Child.agg_from_child_health_case_ucr)


@task
def update_child_table_person_info(domain):
    update_table(domain, 'Child.agg_from_person_case_ucr', Child.agg_from_person_case_ucr)


@task
def update_child_table_household_info(domain):
    update_table(domain, 'Child.agg_from_household_case_ucr', Child.agg_from_household_case_ucr)


@task
def update_child_table_village_info(domain):
    update_table(domain, 'Child.agg_from_village_ucr', Child.agg_from_village_ucr)


@task
def update_child_table_awc_info(domain):
    update_table(domain, 'Child.agg_from_awc_ucr', Child.agg_from_awc_ucr)
