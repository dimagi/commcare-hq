# check all tables have non-empty awc_id
ucrs_with_awc_id = [
    # some awc_id of this UCR are null
    'config_report_icds-cas_static-pregnant-tasks_cases_6c2a698f',
    # some forms are from deleted locations, so loc table doesn't have data on some rows
    'config_report_icds-cas_static-usage_forms_92fbe2aa',
    # some awc_id of this UCR are null
    'config_report_icds-cas_static-awc_mgt_forms_ad1b11f0'
]

child_health_ucrs = [
    # child_health_cases_a46c129f loc table has some empty supervisor_id
    'config_report_icds-cas_dashboard_child_health_daily_fe_f83b12b7',
    'config_report_icds-cas_static-dashboard_thr_forms_b8bca6ea',
    'config_report_icds-cas_static-dashboard_growth_monitor_8f61534c',
    'config_report_icds-cas_static-postnatal_care_forms_0c30d94e',
    'config_report_icds-cas_static-complementary_feeding_fo_4676987e'
]

# some supervisor_id on loc table are null
ccs_record_ucrs = [
    'config_report_icds-cas_static-dashboard_birth_prepared_fd07c11f',
]

# has column 'case_load_ccs_record0'
# some supervisor_id on loc table are null
unclear_ccs_record = ['config_report_icds-cas_static-dashboard_delivery_forms_946d56bd']

ucr_to_sql = [
    # ([ucr_table_list, (join_table_name, ucr_column, join_table_column)])
    (ucrs_with_awc_id, ('config_report_icds-cas_static-awc_location_88b3f9c3', 'awc_id', 'doc_id')),
    (child_health_ucrs, (
        'config_report_icds-cas_static-child_health_cases_a46c129f',
        'child_health_case_id',
        'doc_id')),
    (ccs_record_ucrs, (
        'config_report_icds-cas_static-ccs_record_cases_cedcca39',
        'ccs_record_case_id',
        'doc_id')),
    (unclear_ccs_record, (
        'config_report_icds-cas_static-ccs_record_cases_cedcca39',
        'case_load_ccs_record0',
        'doc_id')),
]


def generate_sql(ucr_table, join_table, ucr_column, join_table_column):
    template = """
    UPDATE "{ucr_table}" ucr
    SET supervisor_id = loc.supervisor_id
    FROM "{join_table}" loc
    WHERE ucr.{ucr_column} = loc.{join_table_column} and ucr.{ucr_column} is NOT NULL
    """
    sql = template.format(
        ucr_table=ucr_table, join_table=join_table,
        ucr_column=ucr_column, join_table_column=join_table_column
    )
    return sql


def get_sql_scripts():
    sql_scripts = {}
    for ucrs, (join_table, ucr_column, join_table_column) in ucr_to_sql:
        for table in ucrs:
            sql_scripts[table] = generate_sql(table, join_table, ucr_column, join_table_column)
    return sql_scripts
