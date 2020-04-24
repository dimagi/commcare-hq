from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management import BaseCommand
from django.db import connections

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
    WHERE t.awc_id = ut.awc_id AND t.month = ut.month AND ut.month='{month}'
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
        parser.add_argument('date', type=date, nargs='?')

    def handle(self, *args, **options):
        date_entered = options["date"] if options["date"] else date(2019, 9, 1)
        self.run_task(date_entered)

    def run_task(self, initial_date):
        final_date = date.today()
        final_date = final_date.replace(day=1)

        monthly_dates = []
        date_itr = initial_date
        while date_itr <= final_date:
            monthly_dates.append(date_itr)
            date_itr = date_itr + relativedelta(months=1)

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
            print(f"====Executing for month f{date}========\n")
            count = 0
            for query in queries:
                print(f"=====Executing query {count} =====\n")
                query = query.format(month=date)
                with connections['icds-ucr-citus'].cursor() as c:
                    c.execute(query)
                count = count + 1
