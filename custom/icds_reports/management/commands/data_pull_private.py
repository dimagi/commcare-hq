import csv
import datetime
from collections import defaultdict

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import connections

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.icds_reports.models import AwcLocation
from custom.icds_reports.utils.connections import get_icds_ucr_citus_db_alias

db_alias = get_icds_ucr_citus_db_alias()

STATE_ID = '3518687a1a6e4b299dedfef967f29c0c'


def _run_custom_sql_script(command):
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)
        return cursor.fetchall()


class Command(BaseCommand):

    def get_district_ids_dict(self):
        filters = {'state_id': STATE_ID, 'aggregation_level': 2}
        locations = AwcLocation.objects.filter(**filters).values('district_id', 'district_name')
        district_names = {}
        for loc in locations:
            district_names[loc['district_id']] = loc['district_name']
        return district_names

    def handle(self, **options):
        query = """
            SELECT "awc_location"."district_id", "child_health_monthly"."child_person_case_id" FROM "public"."child_health_monthly" "child_health_monthly"
            LEFT OUTER JOIN "public"."awc_location" "awc_location" ON (
                ("awc_location"."doc_id" = "child_health_monthly"."awc_id") AND
                ("awc_location"."supervisor_id" = "child_health_monthly"."supervisor_id")
            ) LEFT OUTER JOIN "public"."icds_dashboard_migration_forms" "agg_migration" ON (
                ("child_health_monthly"."child_person_case_id" = "agg_migration"."person_case_id") AND
                ("agg_migration"."month" = '{month}') AND
                ("child_health"."state_id" = "agg_migration"."state_id") AND
                ("child_health"."supervisor_id" = "agg_migration"."supervisor_id")
            ) WHERE "child_health_monthly".month='{month}' AND "awc_location".state_id='{state_id}'
            AND "child_health_monthly"."open_in_month"=1 AND "child_health_monthly"."alive_in_month"=1
            AND "child_health_monthly"."age_tranche" IN ('48', '60', '72')
            AND ("agg_migration"."is_migrated" IS DISTINCT FROM 1 OR "agg_migration"."migration_date"::date >= '{month}');
        """

        months = [datetime.date(2020, 7, 1), datetime.date(2020, 8, 1)]
        case_accessor = CaseAccessors('icds-cas')
        get_district_ids = self.get_district_ids_dict()
        for month in months:
            excel_data = [['district', 'count']]
            person_case_ids = defaultdict(lambda: [])

            for item in _run_custom_sql_script(query.format(month=month, state_id=STATE_ID)):
                person_case_ids[item[0]].append(item[1])

            for key, val in person_case_ids.items():
                count_private_school_going = 0
                district = get_district_ids[key] if key in get_district_ids.keys() else ''
                for case in case_accessor.get_cases(val):
                    date_last_private_admit = case.get_case_property('date_last_private_admit')
                    date_return_private = case.get_case_property('date_return_private')
                    next_month = month + relativedelta(months=1)
                    try:
                        if date_last_private_admit is not None and parser.parse(date_last_private_admit).date() < datetime.datetime(next_month.year, next_month.month, next_month.day):
                            if (not date_return_private) or parser.parse(date_return_private).date() >= datetime.datetime(next_month.year, next_month.month, next_month.day):
                                count_private_school_going += 1
                    except Exception as e:
                        print(e)
                excel_data.append([district, count_private_school_going])
            fout = open(f'/home/cchq/private_students_{month}.csv', 'w')
            writer = csv.writer(fout)
            writer.writerows(excel_data)
