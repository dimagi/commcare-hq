from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.management import BaseCommand
from django.db import connection

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.const import (
    DASHBOARD_DOMAIN
)
from custom.icds_reports.tasks import (
    icds_state_aggregation_task
)

query_text_1 = """
    UPDATE "agg_awc_{month}_5" t
    SET thr_distribution_image_count = ut.thr_distribution_image_count
    FROM  "icds_dashboard_thr_v2" ut
    WHERE t.awc_id = ut.awc_id AND t.month = ut.month;
"""

query_text_2 = """
    UPDATE "agg_awc_{month}_4" t
    SET thr_distribution_image_count = ut.thr_distribution_image_count
    FROM (
        SELECT
            supervisor_id,
            SUM(thr_distribution_image_count) as thr_distribution_image_count
        FROM "agg_awc_{month}_5"
        GROUP BY state_id, district_id,block_id,supervisor_id
    ) ut
    WHERE t.supervisor_id = ut.supervisor_id
"""

query_text_3 = """
    UPDATE "agg_awc_{month}_3" t
    SET thr_distribution_image_count = ut.thr_distribution_image_count
    FROM (
        SELECT
            block_id,
            SUM(thr_distribution_image_count) as thr_distribution_image_count
        FROM "agg_awc_{month}_4"
        GROUP BY state_id, district_id,block_id
    ) ut
    WHERE t.block_id = ut.block_id
"""

query_text_4 = """
    UPDATE "agg_awc_{month}_2" t
    SET thr_distribution_image_count = ut.thr_distribution_image_count
    FROM (
        SELECT
            district_id,
            SUM(thr_distribution_image_count) as thr_distribution_image_count
        FROM "agg_awc_{month}_3"
        GROUP BY state_id, district_id
    ) ut
    WHERE t.district_id = ut.district_id
"""

query_text_5 = """
    UPDATE "agg_awc_{month}_1" t
    SET thr_distribution_image_count = ut.thr_distribution_image_count
    FROM (
        SELECT
            state_id,
            SUM(thr_distribution_image_count) as thr_distribution_image_count
        FROM "agg_awc_{month}_2"
        GROUP BY state_id
    ) ut
    WHERE t.state_id = ut.state_id
"""


class Command(BaseCommand):
    help = "Fills the Missing THR Forms"

    def add_arguments(self, parser):
        parser.add_argument('date', type=str, nargs='?')

    def handle(self, *args, **options):
        date = options["date"] if options["date"] else "2020-09-01"
        date = datetime.strptime(date, '%Y-%m-%d')
        self.run_task(date)

    def run_task(self, initial_date):
        final_date = datetime.now()
        final_date = final_date.replace(day=1)

        # get the number of month intervals between the dates
        intervals = final_date.month - initial_date.month + 12 * (final_date.year - initial_date.year) + 1
        monthly_dates = []
        for i in range(0, intervals):
            monthly_dates.append(initial_date + relativedelta(months=i))

        state_ids = list(
            SQLLocation.objects.filter(domain=DASHBOARD_DOMAIN, location_type__name='state').values_list(
                'location_id', flat=True))
        print("===========Executing int. table creation=====\n")
        for monthly_date in monthly_dates:
            print(f"========{monthly_date}======\n")
            for state_id in state_ids:
                icds_state_aggregation_task(state_id=state_id, date=monthly_date,
                                            func_name='_agg_thr_table')
            date = monthly_date.strftime("%Y-%m-%d")
            queries = [query_text_1, query_text_2, query_text_3, query_text_4, query_text_5]
            print("====Executing for month f{date}========\n")
            count = 0
            for query in queries:
                print("=====Executing query {count} =====\n")
                query = query.format(month=date)
                with connection.cursor() as c:
                    c.execute(query)
                count = count + 1




