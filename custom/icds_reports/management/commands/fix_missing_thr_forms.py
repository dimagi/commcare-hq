from datetime import datetime

from django.core.management import BaseCommand
from django.db import connection

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.const import (
    DASHBOARD_DOMAIN
)
from custom.icds_reports.tasks import (
    _get_monthly_dates,
    icds_state_aggregation_task
)
query_text_0 = """
    DROP TABLE IF EXISTS temp_thr
"""

query_text_1 = """
    CREATE TEMPORARY TABLE "temp_thr" AS 
    SELECT
    awc_location.state_id as state_id,
    awc_location.district_id as district_id,
    awc_location.block_id as block_id,
    awc_location.supervisor_id as supervisor_id,
    awc_location.doc_id AS awc_id,
    thr_v2.thr_distribution_image_count as thr_distribution_image_count
    FROM awc_location_local awc_location
    LEFT JOIN "icds_dashboard_thr_v2" thr_v2 on (awc_location.doc_id = thr_v2.awc_id AND
                                                thr_v2.month = {month}
                                                )
            WHERE awc_location.aggregation_level = 5
"""

query_text_2 = """
    UPDATE "agg_awc_{month}_5" t
    SET t.thr_distribution_image_count = ut.thr_distribution_image_count
    FROM  temp_thr ut
    WHERE t.awc_id = ut.awc_id AND t.aggregation_level = 5
"""

query_text_3 = """
    UPDATE "agg_awc_{month}_4" t
    SET t.thr_distribution_image_count = ut.thr_distribution_image_count
    FROM (
        SELECT
            supervisor_id,
            SUM(thr_distribution_image_count) as thr_distribution_image_count
        FROM "agg_awc_{month}_5"
        GROUP BY state_id, district_id,block_id,supervisor_id;
    ) ut
    WHERE t.supervisor_id = ut.supervisor_id AND t.aggregation_level = 4
"""

query_text_4 = """
    UPDATE "agg_awc_{month}_3" t
    SET t.thr_distribution_image_count = ut.thr_distribution_image_count
    FROM (
        SELECT
            block_id,
            SUM(thr_distribution_image_count) as thr_distribution_image_count
        FROM "agg_awc_{month}_4"
        GROUP BY state_id, district_id,block_id;
    ) ut
    WHERE t.block_id = ut.block_id AND t.aggregation_level = 3
"""

query_text_5 = """
    UPDATE "agg_awc_{month}_2" t
    SET t.thr_distribution_image_count = ut.thr_distribution_image_count
    FROM (
        SELECT
            district_id,
            SUM(thr_distribution_image_count) as thr_distribution_image_count
        FROM "agg_awc_{month}_3"
        GROUP BY state_id, district_id;
    ) ut
    WHERE t.district_id = ut.district_id AND t.aggregation_level = 2
"""

query_text_6 = """
    UPDATE "agg_awc_{month}_1" t
    SET t.thr_distribution_image_count = ut.thr_distribution_image_count
    FROM (
        SELECT
            state_id,
            SUM(thr_distribution_image_count) as thr_distribution_image_count
        FROM "agg_awc_{month}_2"
        GROUP BY state_id, district_id;
    ) ut
    WHERE t.state_id = ut.state_id AND t.aggregation_level = 1
"""


class Command(BaseCommand):
    help = "Fills the Missing THR Forms"

    def handle(self, *args, **kwargs):
        self.run_task()

    def run_task(self):
        initial_date = datetime(2019, 9, 1, 0, 0)
        final_date = datetime.now()
        final_date = final_date.replace(day=1)

        # get the number of month intervals between the dates
        intervals = final_date.month - initial_date.month + 12 * (final_date.year - initial_date.year) + 1
        monthly_dates = _get_monthly_dates(final_date, total_intervals=intervals)

        state_ids = list(
            SQLLocation.objects.filter(domain=DASHBOARD_DOMAIN, location_type__name='state').values_list(
                'location_id', flat=True))
        print("===========Executing int. table creation=====\n")
        for monthly_date in monthly_dates:
            print(f"========{monthly_date}======\n")
            for state_id in state_ids:
                print(f"========{state_id}=======\n")
                icds_state_aggregation_task(state_id=state_id, date=monthly_date,
                                            func_name='_agg_thr_table')
        for monthly_date in monthly_dates:
            date = monthly_date.strftime("%Y-%m-%d")
            queries = [query_text_0, query_text_0, query_text_0, query_text_0, query_text_0, query_text_0]
            print("====Executing for month f{date}========\n")
            count = 0
            for query in queries:
                print("=====Executing query {count} =====\n")
                query = query.format(month=date)
                with connection.cursor() as c:
                    c.execute(query)
                count = count + 1



