from custom.icds_reports.const import AGG_GOV_DASHBOARD_TABLE
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import AggregationPartitionedHelper


class AggGovDashboardHelper(AggregationPartitionedHelper):
    helper_key = 'agg-gov-dashboard'
    base_tablename = AGG_GOV_DASHBOARD_TABLE
    staging_tablename = 'staging_{}'.format(AGG_GOV_DASHBOARD_TABLE)

    @property
    def monthly_tablename(self):
        return "{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"))

    @property
    def previous_agg_table_name(self):
        return f"previous_{self.monthly_tablename}"

    @property
    def model(self):
        from custom.icds_reports.models.aggregate import AggGovernanceDashboard
        return AggGovernanceDashboard

    @property
    def temporary_tablename(self):
        return 'tmp_{}'.format(self.base_tablename)

    def create_temporary_table(self):
        return f"""
        CREATE UNLOGGED TABLE "{self.temporary_tablename}" (LIKE "{self.base_tablename}" INCLUDING INDEXES);
        """

    def drop_temporary_table(self):
        return """
        DROP TABLE IF EXISTS \"{table}\";
        """.format(table=self.temporary_tablename)

    def staging_queries(self):
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
            ('awc_code', 'awc_location_local.awc_site_code'),
            ('month', "'{}'".format(month_formatter(self.month))),
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
        yield """
        INSERT INTO "{tmp_tablename}" (
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
            tmp_tablename=self.temporary_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns])

        ), {
            'start_date': self.month
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
            'start_date': self.month
        }

        yield """
        UPDATE "{tmp_tablename}" agg_gov
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
            tmp_tablename=self.temporary_tablename,
        ), {}

        yield """
        DROP TABLE temp_gov_dashboard;
        """, {}

        yield f"""
                    INSERT INTO "{self.staging_tablename}" SELECT * from "{self.temporary_tablename}";
                """, {
        }

    def indexes(self):
        return []
