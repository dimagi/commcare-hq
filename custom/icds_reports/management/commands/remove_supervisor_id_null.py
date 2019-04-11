from __future__ import absolute_import, print_function
from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from corehq.sql_db.connections import ICDS_UCR_ENGINE_ID, connection_manager


def get_delete_sql(ucr_table):
    return """
    DELETE FROM "{ucr_table}" ucr
    WHERE supervisor_id IS NULL
    """.format(ucr_table=ucr_table)


def get_count_sql(ucr_table):
    return """
    SELECT COUNT(*)
    FROM "{ucr_table}" ucr
    WHERE supervisor_id IS NULL
    """.format(ucr_table=ucr_table)


def get_sql_scripts(delete=False):
    table_names = [
        'ucr_icds-cas_static-pregnant-tasks_cases_6c2a698f',
        'ucr_icds-cas_static-usage_forms_92fbe2aa',
        'ucr_icds-cas_static-child_tasks_cases_3548e54b',
        'ucr_icds-cas_dashboard_child_health_daily_2cd9a7c1',
        'ucr_icds-cas_static-dashboard_growth_moni_4ebf0625',
        'ucr_icds-cas_static-complementary_feeding_f2d76da0',
        'ucr_icds-cas_static-dashboard_birth_prepa_e3e359ff',
        'ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea',
        'ucr_icds-cas_static-postnatal_care_forms_0c30d94e',
        'ucr_icds-cas_static-dashboard_delivery_fo_f079e6e1',
        'child_health_monthly',
        'ccs_record_monthly',
    ]

    sql_scripts = {}
    for table in table_names:
        if delete:
            sql_scripts[table] = get_delete_sql(table)
        else:
            sql_scripts[table] = get_count_sql(table)
    return sql_scripts


class Command(BaseCommand):
    help = "Backfill dashboard UCRs with supervisor_id one by one for each UCR/state_id"

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            dest='delete',
            help='Run delete'
        )

    def handle(self, *args, **options):
        for table_name, sql_script in get_sql_scripts(options['delete']).items():
            session_helper = connection_manager.get_session_helper(ICDS_UCR_ENGINE_ID)
            with session_helper.session_context() as session:
                try:
                    result = session.execute(sql_script)
                except Exception as e:
                    print("{}: {}".format(table_name, e))
                else:
                    if not options['delete']:
                        print("{}: {}".format(table_name, result.fetchone()[0]))
                    else:
                        print("{}: null supervisors deleted".format(table_name))
