import csv
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias
from custom.icds_reports.models import AwcLocation

query_1 = """
    SELECT
        awc_id,
        CASE
            WHEN num_launched_awcs IS DISTINCT FROM 1 THEN 'NOT LAUNCHED'
            WHEN vhnd_conducted>=1 THEN 'YES'
            ELSE 'NO' END as vhnd_conducted_{month}
        FROM "agg_awc_{month_date}_5" WHERE state_id='{state_id}'
"""

query_2 = """
    SELECT
        awc_id,
        COALESCE(count(*), 0) as cbe_conducted_{month},
        STRING_AGG(theme_cbe,',') as type_of_cbe_conducted_{month}
        FROM "ucr_icds-cas_static-cbe_form_f7988a04"
        WHERE
            date_cbe_organise>='{start_date}' AND date_cbe_organise<'{end_date}' AND state_id='{state_id}'
        GROUP BY awc_id
"""

BASE_COLUMNS = [
    "district_name", "block_name", "supervisor_name", "awc_name", "awc_site_code"
]

EXTRA_COLUMNS = [
    "vhnd_conducted", "cbe_conducted", "type_of_cbe_conducted"
]
STATE_ID = '2af81d10b2ca4229a54bab97a5150538'

CBE_MAPPING = {
    "third_fourth_month_of_pregnancy": "Third/Fourth month of pregnancy",
    "annaprasan_diwas": "Annaprasan Diwas",
    "suposhan_diwas": "Suposhan Diwas",
    "coming_of_age": "Celebrating Coming of Age",
    "public_health_message": "Public Health message for Improvement of Nutrition"
}


def _run_custom_sql_script(command):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)
        row = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    return row


class Command(BaseCommand):

    def handle(self, *args, **options):
        start_date = date(2019, 8, 1)
        end_date = date(2020, 3, 1)
        awc_data = AwcLocation.objects.filter(aggregation_level=5, state_id=STATE_ID).values('district_name',
                                                                                             'block_name',
                                                                                             'supervisor_name',
                                                                                             "awc_name",
                                                                                             "awc_site_code",
                                                                                             "doc_id")
        date_itr = start_date
        columns = BASE_COLUMNS.copy()
        while end_date >= date_itr:
            for col in EXTRA_COLUMNS:
                val = f"{col}_{date_itr.strftime('%b_%Y')}"
                val = val.lower()
                columns.append(val)
            date_itr = date_itr + relativedelta(months=1)
        data_format = {}
        for awc in awc_data:
            data_format.update({awc['doc_id']: [awc['district_name'], awc['block_name'], awc['supervisor_name'],
                                                awc['awc_name'], awc['awc_site_code']] + ['-' for _ in range(0,
                                                                                                             len(
                                                                                                                 columns) - len(
                                                                                                                 BASE_COLUMNS))]})
        date_itr = start_date
        while date_itr <= end_date:
            # Agg AWC query
            query_data = _run_custom_sql_script(
                query_1.format(month_date=date_itr.strftime("%Y-%m-%d"), month=date_itr.strftime("%b_%Y"),
                               state_id=STATE_ID))
            for row in query_data:
                awc_id = row['awc_id']
                for k, v in row.items():
                    if v is not None and v != '' and k != 'awc_id':
                        if v == 'NOT LAUNCHED':  # turning rest of the fields to unlaunched
                            data_format[awc_id][columns.index(k) + 1] = v
                            data_format[awc_id][columns.index(k) + 2] = v
                        data_format[awc_id][columns.index(k)] = v
            # CBE ucr query
            query_data = _run_custom_sql_script(
                query_2.format(start_date=date_itr.strftime("%Y-%m-%d"),
                               end_date=(date_itr + relativedelta(months=1)).strftime("%Y-%m-%d"),
                               month=date_itr.strftime("%b_%Y"),
                               state_id=STATE_ID))
            for row in query_data:
                awc_id = row['awc_id']
                for k, v in row.items():
                    if v is not None and v != '' and k != 'awc_id':
                        if data_format[awc_id][columns.index(k)] != 'NOT LAUNCHED':
                            if 'type_of_cbe_conducted' in k:
                                data_format[awc_id][columns.index(k)] = "|".join(
                                    [CBE_MAPPING[i] for i in v.split(',')])
                            else:
                                data_format[awc_id][columns.index(k)] = v
            date_itr = date_itr + relativedelta(months=1)

        final_rows = [columns]
        for k in data_format:
            final_rows.append(data_format[k])

        fout = open(f'maharashtra_vhnsd_cbe.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(final_rows)
