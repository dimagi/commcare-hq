from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_GOV_DASHBOARD_TABLE
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper


class AggGovDashboardHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'agg-gov-dashboard'
    base_tablename = AGG_GOV_DASHBOARD_TABLE

    def __init__(self, month):
        self.month_start = transform_day_to_month(month)
        self.prev_month_start = self.month_start - relativedelta(months=1)
        self.next_month_start = self.month_start + relativedelta(months=1)

    def aggregate(self, cursor):
        drop_table_query = self.drop_table_if_exists()
        cursor.execute(drop_table_query)

        create_table_query, create_params = self.create_child_table()
        cursor.execute(create_table_query, create_params)

        agg_query, agg_params = self.aggregate_query()

        cursor.execute(agg_query, agg_params)

        update_queries = self.update_queries()

        for query, param in update_queries:
            cursor.execute(query, param)

        index_query = self.indexes()
        cursor.execute(index_query)

    @property
    def tablename(self):
        return "{}_{}".format(self.base_tablename, self.month_start.strftime("%Y-%m-%d"))

    def drop_table_if_exists(self):
        return """
        DROP TABLE IF EXISTS "{table_name}"
        """.format(table_name=self.tablename)

    def create_child_table(self):
        return """
        CREATE TABLE "{table_name}" (
        CHECK (month=DATE %(start_date)s)
        ) INHERITS ({base_tablename})
        """.format(
            table_name=self.tablename,
            base_tablename=self.base_tablename,
        ), {
            "start_date": self.month_start
        }

    def aggregate_query(self):
        """
        Returns the base aggregate query which is used to insert all the locations
        into the LS data table.
        """

        columns = (
            ('state_id', 'awc_location_local.state_id'),
            ('district_id', 'awc_location_local.district_id'),
            ('block_id', 'awc_location_local.block_id'),
            ('supervisor_id', 'awc_location_local.supervisor_id'),
            ('awc_id', 'awc_location_local.doc_id'),
            ('awc_site_code', 'awc_location_local.awc_site_code'),
            ('month', "'{}'".format(month_formatter(self.month_start))),
            ('awc_launched', 'agg_awc.num_launched_awcs=1'),
            ('total_preg_benefit_till_date', 'COALESCE(agg_awc.cases_ccs_pregnant, 0)'),
            ('total_lact_benefit_till_date', 'COALESCE(agg_awc.cases_ccs_lactating, 0)'),
            ('total_preg_reg_till_date', 'COALESCE(agg_awc.cases_ccs_pregnant_all,0)'),
            ('total_lact_reg_till_date', 'COALESCE(agg_awc.cases_ccs_lactating_all,0)'),
            ('total_lact_benefit_in_month', 'COALESCE(agg_awc.cases_ccs_lactating_reg_in_month,0)'),
            ('total_preg_benefit_in_month', 'COALESCE(agg_awc.cases_ccs_pregnant_reg_in_month,0)'),
            ('total_lact_reg_in_month', 'COALESCE(agg_awc.cases_ccs_lactating_all_reg_in_month,0)'),
            ('total_preg_reg_in_month', 'COALESCE(agg_awc.cases_ccs_pregnant_all_reg_in_month,0)')
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        )
        (
        SELECT
        {calculations}
        from awc_location_local  LEFT JOIN agg_awc  ON (
            awc_location_local.doc_id = agg_awc.awc_id AND
            awc_location_local.aggregation_level = agg_awc.aggregation_level AND
            agg_awc.month = %(start_date)s
        )
        WHERE awc_location_local.aggregation_level=5 and awc_location_local.state_is_test<>1);
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns])

        ), {
            'start_date': self.month_start
        }

    def update_queries(self):

        yield """
        CREATE UNLOGGED TABLE temp_gov_dashboard AS
            SELECT
                supervisor_id,
                awc_id,
                sum(CASE WHEN sex='F' AND age_tranche::INTEGER<=36 THEN
                    valid_in_month ELSE 0 END ) AS valid_all_0_3_female,
                sum(CASE WHEN sex='M' AND age_tranche::INTEGER<=36 THEN
                    valid_in_month ELSE 0 END ) AS valid_all_0_3_male,
                sum(CASE WHEN sex='F' AND age_tranche::INTEGER<=36 THEN
                    valid_all_registered_in_month ELSE 0 END ) AS open_all_0_3_female,
                sum(CASE WHEN sex='M' AND age_tranche::INTEGER<=36 THEN
                    valid_all_registered_in_month ELSE 0 END ) AS open_all_0_3_male,
                sum(CASE WHEN sex='F' AND age_tranche::INTEGER BETWEEN 37 AND 72 THEN
                    valid_in_month ELSE 0 END ) AS valid_all_3_6_female,
                sum(CASE WHEN sex='M' AND age_tranche::INTEGER BETWEEN 37 AND 72 THEN
                    valid_in_month ELSE 0 END ) AS valid_all_3_6_male,
                sum(CASE WHEN sex='F' AND age_tranche::INTEGER BETWEEN 37 AND 72 THEN
                    valid_all_registered_in_month ELSE 0 END ) AS open_all_3_6_female,
                sum(CASE WHEN sex='M' AND age_tranche::INTEGER BETWEEN 37 AND 72 THEN
                    valid_all_registered_in_month ELSE 0 END ) AS open_all_3_6_male,

                sum(CASE WHEN sex='F' AND age_tranche::INTEGER<=36 AND
                    date_trunc('month',opened_on)=%(start_date)s THEN
                    valid_in_month ELSE 0 END ) AS valid_reg_in_month_0_3_female,
                sum(CASE WHEN sex='M' AND age_tranche::INTEGER<=36 AND
                    date_trunc('month',opened_on)=%(start_date)s THEN
                    valid_in_month ELSE 0 END ) AS valid_reg_in_month_0_3_male,
                sum(CASE WHEN sex='F' AND age_tranche::INTEGER<=36 AND
                    date_trunc('month',opened_on)=%(start_date)s THEN
                    valid_all_registered_in_month ELSE 0 END ) AS open_reg_in_month_0_3_female,

                sum(CASE WHEN sex='M' AND age_tranche::INTEGER<=36 AND
                    date_trunc('month',opened_on)=%(start_date)s THEN
                    valid_all_registered_in_month ELSE 0 END ) AS open_reg_in_month_0_3_male,

                sum(CASE WHEN sex='F' AND age_tranche::INTEGER BETWEEN 37 AND 72 AND
                    date_trunc('month',opened_on)=%(start_date)s THEN
                    valid_in_month ELSE 0 END ) AS valid_reg_in_month_3_6_female,
                sum(CASE WHEN sex='M' AND age_tranche::INTEGER BETWEEN 37 AND 72 AND
                    date_trunc('month',opened_on)=%(start_date)s THEN
                    valid_in_month ELSE 0 END ) AS valid_reg_in_month_3_6_male,

                sum(CASE WHEN sex='F' AND age_tranche::INTEGER BETWEEN 37 AND 72 AND
                    date_trunc('month',opened_on)=%(start_date)s THEN
                    valid_all_registered_in_month ELSE 0 END ) AS  open_reg_in_month_3_6_female,

                sum(CASE WHEN sex='M' AND age_tranche::INTEGER BETWEEN 37 AND 72 AND
                    date_trunc('month',opened_on)=%(start_date)s THEN
                    valid_all_registered_in_month ELSE 0 END ) AS  open_reg_in_month_3_6_male
            FROM child_health_monthly
            WHERE month=%(start_date)s
            GROUP BY supervisor_id, awc_id;
        """, {
            'start_date': self.month_start
        }

        yield """
        UPDATE "{tablename}" agg_gov
        SET total_0_3_female_benefit_till_date = ut.valid_all_0_3_female,
            total_0_3_male_benefit_till_date = ut.valid_all_0_3_male,
            total_0_3_female_reg_till_date = ut.open_all_0_3_female,
            total_0_3_male_reg_till_date = ut.open_all_0_3_male,
            total_3_6_female_benefit_till_date = ut.valid_all_3_6_female,
            total_3_6_male_benefit_till_date = ut.valid_all_3_6_male,
            total_3_6_female_reg_till_date = ut.open_all_3_6_female,
            total_3_6_male_reg_till_date = ut.open_all_3_6_male,
            total_0_3_female_benefit_in_month = ut.valid_reg_in_month_0_3_female,
            total_0_3_male_benefit_in_month = ut.valid_reg_in_month_0_3_male,
            total_0_3_female_reg_in_month = ut.open_reg_in_month_0_3_female,
            total_0_3_male_reg_in_month = ut.open_reg_in_month_0_3_male,
            total_3_6_female_benefit_in_month = ut.valid_reg_in_month_3_6_female,
            total_3_6_male_benfit_in_month = ut.valid_reg_in_month_3_6_male,
            total_3_6_female_reg_in_month = ut.open_reg_in_month_3_6_female,
            total_3_6_male_reg_in_month = ut.open_reg_in_month_3_6_male
        FROM temp_gov_dashboard ut
        WHERE agg_gov.awc_id = ut.awc_id;
        """.format(
            tablename=self.tablename,
        ), {}

        yield """
        DROP TABLE temp_gov_dashboard;
        """, {}

    def indexes(self):
        """
        Returns query to create index with columns month, state_id and awc_id
        """
        return 'CREATE INDEX ON "{}" (month, state_id, awc_id)'.format(self.tablename)
