import csv
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias



query_1 = """
    SELECT
        district_id,
        num_launched_districts as num_launched_districts_{month},
        num_launched_blocks as num_launched_blocks_{month},
        num_launched_awcs as num_launched_awcs_{month},
        awc_days_open/25 as awc_open_percent_{month},
        wer_weighed as wer_weighed_{month},
        wer_eligible as wer_eligible_{month},
        CASE WHEN wer_eligible>0 THEN wer_weighed/wer_eligible::float*100 ELSE 0 END as wer_percentage_{month}
        FROM agg_awc_{month_date}
    WHERE aggregation_level=2
"""

query_2 = """
    SELECT
        district_id,
        pse_eligible as pse_eligible_{month},
        pse_attended_21_days as pse_attended_21_days_{month},
        CASE WHEN pse_eligible>0 THEN pse_attended_21_days/pse_eligible::float*100 ELSE 0 END as pse_percentange_{month},
        height_eligible as height_eligible_{month},
        height_measured_in_month as height_measured_in_month_{month},
        pse_eligible as lunch_eligible_{month},
        CASE height_eligible>0 THEN height_measured_in_month/height_eligible::float*100 ELSE 0 END as height_percentage_{month},
        lunch_count_21_days as lunch_count_21_days_{month},
        CASE WHEN pse_eligible>0 THEN lunch_count_21_days/pse_eligible::float*100 ELSE 0 END as lunch_percentage_{month},
        thr_eligible as thr_eligible_{month},
        rations_21_plus_distributed as rations_21_plus_distributed_{month},
        FROM agg_child_health_{month_date}
        WHERE aggregation_level=2
"""

query_3 = """
    SELECT
        district_id,
        rations_21_plus_distributed as rations_21_plus_distributed_{month},
        thr_eligible as thr_eligible_{month},
        trimester_3 as trimester_3_{month},
        counsel_immediate_bf as counsel_immediate_bf_{month},
        CASE WHEN trimester_3>0 THEN counsel_immediate_bf/trimester_3::float*100 ELSE 0 END as percent_trimester_{month}
    FROM agg_ccs_record_{month_date} and aggregation_level=2
"""

columns = [
    "state_name", "district_name",
    "num_launched_districts_January", "num_launched_districts_February", "num_launched_districts_March",
    "num_launched_blocks_January", "num_launched_blocks_February", "num_launched_blocks_March",
    "num_launched_awcs_January", "num_launched_awcs_February", "num_launched_awcs_March",
    "awc_open_percent_January", "awc_open_percent_February", "awc_open_percent_March",
    "pse_eligible_January", "pse_eligible_February", "pse_eligible_March",
    "pse_attended_21_days_January", "pse_attended_21_days_February", "pse_attended_21_days_March"
    "pse_percentange_January", "pse_percentange_February", "pse_percentange_March",
    "wer_eligible_January", "wer_eligible_February", "wer_eligible_March",
    "wer_weighed_January", "wer_weighed_February", "wer_weighed_March",
    "wer_percentage_January", "wer_percentage_February", "wer_percentage_March",
    "trimester_3_January", "trimester_3_February", "trimester_3_March",
    "counsel_immediate_bf_January", "counsel_immediate_bf_February", "counsel_immediate_bf_March",
    "percent_trimester_January", "percent_trimester_February", "percent_trimester_March",
    "height_eligible_January", "height_eligible_February", "height_eligible_March",
    "height_measured_in_month_January", "height_measured_in_month_February", "height_measured_in_month_March",
    "height_percentage_January", "height_percentage_February", "height_percentage_March",
    "thr_eligible_January", "thr_eligible_February", "thr_eligible_March",
    "rations_21_plus_distributed_January", "rations_21_plus_distributed_February", "rations_21_plus_distributed_March",
    "lunch_eligible_January", "lunch_eligible_February", "lunch_eligible_March",
    "lunch_count_21_days_January", "lunch_count_21_days_February", "lunch_count_21_days_March",
    "lunch_percentage_January", "lunch_percentage_February", "lunch_percentage_March"
]



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
        start_date = date(2020, 1, 1)
        end_date = date(2020, 3, 1)
        date_itr = start_date
        awc_data = AwcLocation.objects.filter(aggregation_level=2).values('district_id', 'district_name', 'state_name')
        queries = [query_1, query_2, query_3]
        data_format = {}
        for awc in awc_data:
            data_format.update({awc['district_id']: [awc['district_name'], awc['state_name']] + [0 for _ in range(0, len(columns)-2)]})

        while date_itr <= end_date:
            for query in queries:
                query_data = _run_custom_sql_script(query.format(month_date=date_itr.strftime("%Y-%m-%d"), month=date_itr.strftime("%B")))
                for row in query_data:
                    district_id = row['district_id']
                    for k, v in row.items():
                        if v is not None or v != '' and k != 'district_id':
                            data_format[district_id][columns.index(k)] = data_format[district_id][columns.index(k)] + v
            date_itr = date_itr + relativedelta(months=1)

        final_rows = [columns]
        for k in data_format:
            final_rows.append(data_format[k])

        fout = open(f'/home/cchq/build_progress_report.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(final_rows)
