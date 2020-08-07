from dateutil.relativedelta import relativedelta
from django.db import connections

from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.utils.connections import get_icds_ucr_citus_db_alias
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.utils.aggregation_helpers import get_prev_agg_tablename, transform_day_to_month


class TempPrevTablesBase(object):

    DROP_QUERY = """
    DROP TABLE IF EXISTS "{prev_table}";
    DROP TABLE IF EXISTS "{prev_local}";
    """

    def drop_temp_tables(self, alias):
        data = {
            'prev_table': get_prev_agg_tablename(alias),
            'prev_local': f"{alias}_prev_local",
        }
        with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
            cursor.execute(self.DROP_QUERY.format(**data))

    def create_temp_tables(self, alias, table, day):
        data = {
            'prev_table': get_prev_agg_tablename(alias),
            'prev_local': f"{alias}_prev_local",
            'prev_month': day,
            'current_table': table,
            'alias': alias
        }
        with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
            cursor.execute(self.CREATE_QUERY.format(**data))

    def make_all_tables(self, day):
        raise NotImplementedError


class TempPrevUCRTables(TempPrevTablesBase):

    CREATE_QUERY = """
    CREATE UNLOGGED TABLE "{prev_table}" (LIKE "{current_table}");
    SELECT create_distributed_table('{prev_table}', 'supervisor_id');
    INSERT INTO "{prev_table}" (SELECT * FROM "{current_table}");
    CREATE INDEX "idx_reassignment_date_{alias}" ON "{prev_table}" USING hash (location_reassignment_date);
    CREATE UNLOGGED TABLE "{prev_local}" AS (SELECT * FROM "{current_table}" WHERE date_trunc('MONTH', location_reassignment_date)='{prev_month}');
    UPDATE "{prev_local}" SET supervisor_id = last_supervisor_id, awc_id=last_owner_id, location_reassignment_date=date_trunc('MONTH', location_reassignment_date);
    DELETE FROM "{prev_table}" WHERE location_reassignment_date='{prev_month}';
    INSERT INTO "{prev_table}" (SELECT * FROM "{prev_local}");
    """

    def drop_temp_tables(self, alias):
        data = {
            'prev_table': get_prev_agg_tablename(alias),
            'prev_local': f"{alias}_prev_local",
        }
        with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
            cursor.execute(self.DROP_QUERY.format(**data))

    def create_temp_tables(self, table, day):
        data = {
            'prev_table': get_prev_agg_tablename(table),
            'prev_local': f"{table}_prev_local",
            'prev_month': day,
            'current_table': get_table_name(DASHBOARD_DOMAIN, table),
            'alias': table
        }
        with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
            cursor.execute(self.CREATE_QUERY.format(**data))

    def make_all_tables(self, day):
        day = transform_day_to_month(day) + relativedelta(months=1)
        table_list = [
            'static-child_health_cases',
            'static-ccs_record_cases',
            'static-person_cases_v3',
            'static-household_cases',
            'static-child_tasks_cases',
            'static-pregnant-tasks_cases',
        ]
        for table in table_list:
            self.drop_temp_tables(table)
            self.create_temp_tables(table, day)


class TempPrevIntermediateTables(TempPrevTablesBase):
    CREATE_QUERY = """
    CREATE UNLOGGED TABLE "{prev_table}" (LIKE "{current_table}");
    SELECT create_distributed_table('{prev_table}', 'supervisor_id');
    INSERT INTO "{prev_table}" (SELECT * FROM "{current_table}" where month='{prev_month}');
    CREATE INDEX "idx_sup_case_{alias}" ON "{prev_table}" USING hash ({id_column});
    CREATE INDEX "idx_sup_state_{alias}" ON "{prev_table}" USING hash (state_id);
    CREATE UNLOGGED TABLE "{prev_local}" AS (SELECT * FROM "{current_table}" WHERE {id_column} in (select doc_id from "{ucr_prev_local}"));
    DELETE FROM "{prev_table}" WHERE {id_column} in (select doc_id from "{ucr_prev_local}");
    UPDATE "{prev_local}" prev SET supervisor_id = last_supervisor_id FROM "{ucr_prev_local}" ucr WHERE prev.{id_column}=ucr.doc_id;
    INSERT INTO "{prev_table}" (SELECT * FROM "{prev_local}");
    """
    table_list = [
        ('postnatal-care-forms-child-health', 'icds_dashboard_child_health_postnatal_forms', 'static-child_health_cases', 'case_id'),
        ('growth-monitoring-forms', 'icds_dashboard_growth_monitoring_forms', 'static-child_health_cases', 'case_id'),
        ('birth-preparedness-forms', 'icds_dashboard_ccs_record_bp_forms', 'static-ccs_record_cases', 'case_id'),
        ('postnatal-care-forms-ccs-record', 'icds_dashboard_ccs_record_postnatal_forms', 'static-ccs_record_cases', 'case_id'),
        ('complementary-forms-ccs-record', 'icds_dashboard_ccs_record_cf_forms', 'static-ccs_record_cases', 'case_id'),
        ('complementary-forms', 'icds_dashboard_comp_feed_form', 'static-child_health_cases', 'case_id'),
        ('migration-forms', 'icds_dashboard_migration_forms', 'static-person_cases_v3', 'person_case_id'),
        ('availing_service-forms', 'icds_dashboard_availing_service_forms', 'static-person_cases_v3', 'person_case_id'),
        ('adolescent-girls', 'icds_dashboard_adolescent_girls_registration', 'static-person_cases_v3', 'person_case_id'),
    ]

    def create_temp_tables(self, table, day):
        alias, table, ucr_alias, id_column_name = table
        data = {
            'prev_table': get_prev_agg_tablename(alias),
            'prev_local': f"{alias}_prev_local",
            'prev_month': day,
            'current_table': table,
            'alias': alias,
            'ucr_prev_local': f"{ucr_alias}_prev_local",
            'id_column': id_column_name
        }
        with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
            cursor.execute(self.CREATE_QUERY.format(**data))

    def make_all_tables(self, day):
        day = transform_day_to_month(day) - relativedelta(months=1)
        for table in self.table_list:
            self.drop_temp_tables(table[0])
            self.create_temp_tables(table, day)


class TempInfraTables(TempPrevTablesBase):
    CREATE_QUERY = """
    CREATE UNLOGGED TABLE "{prev_table}" (LIKE "{current_table}");
    INSERT INTO "{prev_table}" (SELECT * FROM "{current_table}" where timeend >= '{six_months_ago}' AND timeend < '{next_month_start}');
    CREATE INDEX "idx_sup_state_{alias}" ON "{prev_table}" USING hash (state_id);
    CREATE UNLOGGED TABLE "{prev_local}" AS (SELECT * FROM "{current_table}" WHERE awc_id in (select doc_id from awc_location_local where aggregation_level=5 and awc_deprecated_at  >= '{prev_month}' AND awc_deprecated_at < '{next_month_start}'));
    DELETE FROM "{prev_table}" WHERE awc_id in (select awc_id from "{prev_local}");
    UPDATE "{prev_local}" prev SET
        supervisor_id = awc.supervisor_id,
        awc_id=awc.awc_id
    FROM (
        SELECT
            unnest(string_to_array(awc_deprecates, ',')) as prev_awc_id,
            doc_id as awc_id, supervisor_id
        FROM "awc_location_local" awc
        WHERE awc_deprecated_at  >= '{prev_month}' AND
              awc_deprecated_at < '{next_month_start}' AND
              aggregation_level=5) awc
    WHERE prev.awc_id=awc.prev_awc_id;
    INSERT INTO "{prev_table}" (SELECT * FROM "{prev_local}");
    """

    def create_temp_tables(self, table, day):
        next_month_start = day + relativedelta(months=1)
        six_months_ago = day - relativedelta(months=6)
        alias, table = table
        data = {
            'prev_table': get_prev_agg_tablename(alias),
            'prev_local': f"{alias}_prev_local",
            'prev_month': day,
            'current_table': table,
            'alias': alias,
            'six_months_ago': six_months_ago,
            'next_month_start': next_month_start
        }
        with connections[get_icds_ucr_citus_db_alias()].cursor() as cursor:
            cursor.execute(self.CREATE_QUERY.format(**data))

    def make_all_tables(self, day):
        day = transform_day_to_month(day)
        table_list = [
            ('static-infrastructure_form_v2', get_table_name(DASHBOARD_DOMAIN, 'static-infrastructure_form_v2'))
        ]
        for table in table_list:
            self.drop_temp_tables(table[0])
            self.create_temp_tables(table, day)
