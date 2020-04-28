import os


from django.core.management.base import BaseCommand
from django.db import connections, transaction
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


@transaction.atomic
def _run_custom_sql_script(command, day=None):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command, [day])


class Command(BaseCommand):

    def build_data(self, context):
        for i in range(1, 3):
            path = os.path.join(os.path.dirname(__file__), 'sql_scripts',
                                'district_data_pull_{}.sql'.format(i))
            with open(path, "r", encoding='utf-8') as sql_file:
                sql_to_execute = sql_file.read()
                sql_to_execute = sql_to_execute % context
                print(f"Executing Pull district_date_pull_{i} {context['name']}\n")
                print(sql_to_execute)
                print("-----------------------------------------------------\n")
                _run_custom_sql_script(sql_to_execute)

    def handle(self, *args, **kwargs):
        self.run_task()

    def run_task(self):
        batches = [
            {
                "name": "april_2019_june_2019",
                "column_1": "april_2019",
                "column_2": "may_2019",
                "column_3": "june_2019",
                "month_1": "2019-04-01",
                "month_2": "2019-05-01",
                "month_3": "2019-06-01"
            },
            {
                "name": "july_2019_september_2019",
                "column_1": "july_2019",
                "column_2": "august_2019",
                "column_3": "september_2019",
                "month_1": "2019-07-01",
                "month_2": "2019-08-01",
                "month_3": "2019-09-01"
            },
            {
                "name": "october_2019_december_2019",
                "column_1": "october_2019",
                "column_2": "november_2019",
                "column_3": "december_2019",
                "month_1": "2019-10-01",
                "month_2": "2019-11-01",
                "month_3": "2019-12-01"
            },
            {
                "name": "january_2020_march_2020",
                "column_1": "january_2020",
                "column_2": "february_2020",
                "column_3": "march_2020",
                "month_1": "2020-01-01",
                "month_2": "2020-02-01",
                "month_3": "2020-03-01"
            }
        ]

        for batch in batches:
            self.build_data(batch)
