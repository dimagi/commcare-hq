from __future__ import absolute_import, unicode_literals

from datetime import datetime

from celery.task import task
from dateutil.relativedelta import relativedelta
from django.db import connections

from custom.aaa.models import (
    AggAwc,
    AggregationInformation,
    AggVillage,
    CcsRecord,
    Child,
    ChildHistory,
    Woman,
    WomanHistory,
)


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
def update_child_table(domain):
    for agg_query in Child.aggregation_queries:
        update_table(domain, Child.__name__ + agg_query.__name__, agg_query)


@task
def update_child_history_table(domain):
    for agg_query in ChildHistory.aggregation_queries:
        update_table(domain, ChildHistory.__name__ + agg_query.__name__, agg_query)


@task
def update_woman_table(domain):
    for agg_query in Woman.aggregation_queries:
        update_table(domain, Woman.__name__ + agg_query.__name__, agg_query)


@task
def update_woman_history_table(domain):
    for agg_query in WomanHistory.aggregation_queries:
        update_table(domain, Woman.__name__ + agg_query.__name__, agg_query)


@task
def update_ccs_record_table(domain):
    for agg_query in CcsRecord.aggregation_queries:
        update_table(domain, CcsRecord.__name__ + agg_query.__name__, agg_query)


def update_monthly_table(domain, slug, method, month):
    window_start = month.replace(day=1)
    window_end = window_start + relativedelta(months=1)
    agg_info = AggregationInformation.objects.create(
        domain=domain,
        step=slug,
        aggregation_window_start=window_start,
        aggregation_window_end=window_end,
    )

    agg_query, agg_params = method(domain, window_start, window_end)
    with connections['aaa-data'].cursor() as cursor:
        cursor.execute(agg_query, agg_params)
    agg_info.end_time = datetime.utcnow()
    agg_info.save()


@task
def update_agg_awc_table(domain, month):
    for agg_query in AggAwc.aggregation_queries:
        update_monthly_table(domain, AggAwc.__name__ + agg_query.__name__, agg_query, month)


@task
def update_agg_village_table(domain, month):
    for agg_query in AggVillage.aggregation_queries:
        update_monthly_table(domain, AggVillage.__name__ + agg_query.__name__, agg_query, month)
