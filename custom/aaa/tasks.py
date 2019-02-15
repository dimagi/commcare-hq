from __future__ import absolute_import, unicode_literals

from datetime import datetime


from celery.task import task
from dateutil.relativedelta import relativedelta
from django.db import connections

from custom.aaa.models import AggAwc, AggregationInformation, AggVillage, CcsRecord, Child, Woman


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


@task
def update_woman_table_ccs_record_info(domain):
    update_table(domain, 'Woman.agg_from_ccs_record_case_ucr', Woman.agg_from_ccs_record_case_ucr)


@task
def update_woman_table_person_info(domain):
    update_table(domain, 'Woman.agg_from_person_case_ucr', Woman.agg_from_person_case_ucr)


@task
def update_woman_table_household_info(domain):
    update_table(domain, 'Woman.agg_from_household_case_ucr', Woman.agg_from_household_case_ucr)


@task
def update_woman_table_village_info(domain):
    update_table(domain, 'Woman.agg_from_village_ucr', Woman.agg_from_village_ucr)


@task
def update_woman_table_awc_info(domain):
    update_table(domain, 'Woman.agg_from_awc_ucr', Woman.agg_from_awc_ucr)


@task
def update_ccs_record_table_ccs_record_info(domain):
    update_table(domain, 'CcsRecord.agg_from_ccs_record_case_ucr', CcsRecord.agg_from_ccs_record_case_ucr)


@task
def update_ccs_record_table_person_info(domain):
    update_table(domain, 'CcsRecord.agg_from_person_case_ucr', CcsRecord.agg_from_person_case_ucr)


@task
def update_ccs_record_table_household_info(domain):
    update_table(domain, 'CcsRecord.agg_from_household_case_ucr', CcsRecord.agg_from_household_case_ucr)


@task
def update_ccs_record_table_village_info(domain):
    update_table(domain, 'CcsRecord.agg_from_village_ucr', CcsRecord.agg_from_village_ucr)


@task
def update_ccs_record_table_awc_info(domain):
    update_table(domain, 'CcsRecord.agg_from_awc_ucr', CcsRecord.agg_from_awc_ucr)


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
    update_monthly_table(domain, 'AggAwc.agg_from_woman_table', AggAwc.agg_from_woman_table, month)
    update_monthly_table(domain, 'AggAwc.agg_from_ccs_record_table', AggAwc.agg_from_ccs_record_table, month)
    update_monthly_table(domain, 'AggAwc.agg_from_child_table', AggAwc.agg_from_child_table, month)
    update_monthly_table(domain, 'AggAwc.rollup_supervisor', AggAwc.rollup_supervisor, month)
    update_monthly_table(domain, 'AggAwc.rollup_block', AggAwc.rollup_block, month)
    update_monthly_table(domain, 'AggAwc.rollup_district', AggAwc.rollup_district, month)
    update_monthly_table(domain, 'AggAwc.rollup_state', AggAwc.rollup_state, month)
    update_monthly_table(domain, 'AggAwc.rollup_national', AggAwc.rollup_national, month)


@task
def update_agg_village_table(domain, month):
    update_monthly_table(domain, 'AggVillage.agg_from_woman_table', AggVillage.agg_from_woman_table, month)
    update_monthly_table(domain, 'AggVillage.agg_from_ccs_record_table', AggVillage.agg_from_ccs_record_table, month)
    update_monthly_table(domain, 'AggVillage.agg_from_child_table', AggVillage.agg_from_child_table, month)
    update_monthly_table(domain, 'AggVillage.rollup_sc', AggVillage.rollup_sc, month)
    update_monthly_table(domain, 'AggVillage.rollup_phc', AggVillage.rollup_phc, month)
    update_monthly_table(domain, 'AggVillage.rollup_taluka', AggVillage.rollup_taluka, month)
    update_monthly_table(domain, 'AggVillage.rollup_district', AggVillage.rollup_district, month)
    update_monthly_table(domain, 'AggVillage.rollup_state', AggVillage.rollup_state, month)
    update_monthly_table(domain, 'AggVillage.rollup_national', AggVillage.rollup_national, month)
