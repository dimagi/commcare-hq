import datetime
from dateutil import parser
from django.core.management.base import BaseCommand
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from django.db import connections, transaction
from dateutil.relativedelta import relativedelta
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias

db_alias = get_icds_ucr_citus_db_alias()


def _run_custom_sql_script(command):
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)
        return cursor.fetchall()


class Command(BaseCommand):

    def handle(self, **options):
        query = """
            SELECT child_person_case_id from child_health_monthly
            where pse_eligible=1 and age_trance='{age_group}' and month='{month}';
        """

        months = [datetime.date(2020, 1, 1), datetime.date(2020, 2, 1), datetime.date(2020, 3, 1)]
        case_accessor = CaseAccessors('icds-cas')

        for month in months:
            for age_group in ('48', '60', '72'):

                count_primary_school_going = 0
                count_private_school_going = 0
                count_joined_primary_school_during_month = 0
                count_joined_private_school_during_month = 0
                count_stopped_private_school_during_month = 0
                total_count = 0
                person_case_ids = [item[0] for item in _run_custom_sql_script(query.format(age_group=age_group,month=month))]

                for case in case_accessor.iter_cases(person_case_ids):
                    total_count += 1
                    primary_school_admit = case.get_case_property('primary_school_admit')
                    date_primary_admit = case.get_case_property('date_primary_admit')
                    date_last_private_admit = case.get_case_property('date_last_private_admit')
                    date_return_private = case.get_case_property('date_return_private')
                    next_month = month + relativedelta(months=1)
                    if primary_school_admit == 'yes' and parser.parse(date_primary_admit) < next_month:
                        count_primary_school_going += 1

                    if date_last_private_admit is not None and parser.parse(date_last_private_admit) < next_month and \
                        (date_return_private is None or parser.parse(date_return_private) >= next_month):
                        count_private_school_going += 1

                    if primary_school_admit == 'yes' and parser.parse(date_primary_admit) >= month and parser.parse(date_primary_admit) < next_month:
                        count_joined_primary_school_during_month += 1

                    if date_last_private_admit is not None and  parser.parse(date_last_private_admit) >= month and parser.parse(date_last_private_admit)< next_month:
                        count_joined_private_school_during_month += 1

                    if date_return_private is not None and parser.parse(date_return_private) >= month and parser.parse(date_return_private) < next_month:
                        count_stopped_private_school_during_month += 1

                count_children_pse_in_awc = len(total_count) - count_primary_school_going - count_private_school_going
                print("DATA FOR MONTH {} and age group {}".format(month, age_group))
                print("Public School Going Children : {}".format(count_primary_school_going))
                print("Private School Going Children: {}".format(count_private_school_going))
                print("Children attending PSE in AWC: {}".format(count_children_pse_in_awc))
                print("Children started going to Public School in month: {}".format(count_joined_primary_school_during_month))
                print("Children started going to Private School in month: {}".format(count_joined_private_school_during_month))
                print("Children stopped going to Private School in month: {}".format(count_stopped_private_school_during_month))
