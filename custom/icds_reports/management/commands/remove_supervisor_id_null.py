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
        'ucr_icds-cas_dashboard_child_health_daily_2cd9a7c1',
        'ucr_icds-cas_static-awc_location_88b3f9c3',
        'ucr_icds-cas_static-awc_mgt_forms_ad1b11f0',
        'ucr_icds-cas_static-cbe_form_f7988a04',
        'ucr_icds-cas_static-ccs_record_cases_cedcca39',
        'ucr_icds-cas_static-ccs_record_cases_mont_22b3ea30',
        'ucr_icds-cas_static-child_delivery_forms_eafd4095',
        'ucr_icds-cas_static-child_health_cases_a46c129f',
        'ucr_icds-cas_static-child_tasks_cases_3548e54b',
        'ucr_icds-cas_static-commcare_user_cases_85763310',
        'ucr_icds-cas_static-complementary_feeding_f2d76da0',
        'ucr_icds-cas_static-daily_feeding_forms_85b1167f',
        'ucr_icds-cas_static-dashboard_birth_prepa_e3e359ff',
        'ucr_icds-cas_static-dashboard_delivery_fo_f079e6e1',
        'ucr_icds-cas_static-dashboard_growth_moni_4ebf0625',
        'ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea',
        'ucr_icds-cas_static-household_cases_eadc276d',
        'ucr_icds-cas_static-infrastructure_form_05fe0f1a',
        'ucr_icds-cas_static-infrastructure_form_v_9918f894',
        'ucr_icds-cas_static-ls_home_visit_forms_f_dff88f6d',
        'ucr_icds-cas_static-ls_vhnd_form_f2b97e26',
        'ucr_icds-cas_static-person_cases_v3_2ae0879a',
        'ucr_icds-cas_static-postnatal_care_forms_0c30d94e',
        'ucr_icds-cas_static-pregnant-tasks_cases_6c2a698f',
        'ucr_icds-cas_static-thr_forms_v2_7f2a03ba',
        'ucr_icds-cas_static-usage_forms_92fbe2aa',
        'ucr_icds-cas_static-vhnd_form_28e7fd58',
        'child_health_monthly',
        'ccs_record_monthly',

        # non dashboard tables
        'ucr_icds-cas_static-ccs_record_cases_mont_6c60c6dd',
        'ucr_icds-cas_static-child_cases_monthly_v_c7032e8d',
        'ucr_icds-cas_static-gm_forms_2325944e',
        'ucr_icds-cas_static-home_visit_forms_02056025',
        'ucr_icds-cas_static-visitorbook_forms_76e9914e',
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
