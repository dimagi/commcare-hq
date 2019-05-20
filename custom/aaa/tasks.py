from __future__ import absolute_import, unicode_literals

from datetime import datetime

from celery.task import task
from dateutil.relativedelta import relativedelta
from django.db import connections


from corehq.sql_db.connections import get_aaa_db_alias
from custom.aaa.dbaccessors import EligibleCoupleQueryHelper, PregnantWomanQueryHelper, ChildQueryHelper
from custom.aaa.models import (
    AggAwc,
    AggregationInformation,
    AggVillage,
    CcsRecord,
    Child,
    ChildHistory,
    DenormalizedAWC,
    DenormalizedVillage,
    Woman,
)
from custom.aaa.utils import build_location_filters, create_excel_file
from dimagi.utils.dates import force_to_date


@task
def run_aggregation(domain, month=None):
    update_location_tables(domain)
    update_child_table(domain)
    update_child_history_table(domain)
    update_woman_table(domain)
    update_ccs_record_table(domain)
    if month:
        update_agg_awc_table(domain, month)
        update_agg_village_table(domain, month)


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
    db_alias = get_aaa_db_alias()
    with connections[db_alias].cursor() as cursor:
        cursor.execute(agg_query, agg_params)
    agg_info.end_time = datetime.utcnow()
    agg_info.save()


@task
def update_location_tables(domain):
    DenormalizedAWC.build(domain)
    DenormalizedVillage.build(domain)


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
    db_alias = get_aaa_db_alias()
    with connections[db_alias].cursor() as cursor:
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


@task
def prepare_export_reports(domain, selected_date, next_month_start, selected_location,
                           selected_ministry, beneficiary_type):
    location_filters = build_location_filters(selected_location, selected_ministry, with_child=False)
    sort_column = 'name'

    selected_date = force_to_date(selected_date)
    next_month_start = force_to_date(next_month_start)

    columns = []
    data = []

    if beneficiary_type == 'child':
        columns = (
            ('name', 'Name'),
            ('age_in_months', 'Age (in Months)'),
            ('gender', 'Gender'),
            ('lastImmunizationType', 'Last Immunization Type'),
            ('lastImmunizationDate', 'Last Immunization Date'),
        )
        data = ChildQueryHelper.list(domain, next_month_start, location_filters, sort_column)
    elif beneficiary_type == 'eligible_couple':
        columns = (
            ('name', 'Name'),
            ('age_in_months', 'Age (in Months)'),
            ('currentFamilyPlanningMethod', 'Current Family Planing Method'),
            ('adoptionDateOfFamilyPlaning', 'Adoption Date Of Family Planning'),
        )
        data = EligibleCoupleQueryHelper.list(domain, selected_date, location_filters, sort_column)
    elif beneficiary_type == 'pregnant_women':
        columns = (
            ('name', 'Name'),
            ('age_in_months', 'Age (in Months)'),
            ('pregMonth', 'Preg. Month'),
            ('highRiskPregnancy', 'High Risk Pregnancy'),
            ('noOfAncCheckUps', 'No. Of ANC Check-Ups'),
        )
        data = PregnantWomanQueryHelper.list(domain, selected_date, location_filters, sort_column)

    export_columns = [col[1] for col in columns]

    export_data = [export_columns]
    for row in data:
        row_data = [row[col[0]] or 'N/A' for col in columns]
        export_data.append(row_data)
    return create_excel_file(
        domain,
        [[beneficiary_type, export_data]],
        beneficiary_type,
        'xlsx'
    )
