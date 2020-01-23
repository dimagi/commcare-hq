from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_GOV_DASHBOARD_TABLE
from custom.icds_reports.utils.aggregation_helpers import  month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import AggregationPartitionedHelper


class AggGovDashboardHelper(AggregationPartitionedHelper):
    helper_key = 'agg-gov-dashboard'
    base_tablename = AGG_GOV_DASHBOARD_TABLE
    ucr_data_source_id = 'static_vhnd_form'
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

    def update_queries(self):
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
            tmp_tablename=self.staging_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns])

        ), {
            'start_date': self.month
        }

        yield """
        CREATE TABLE temp_gov_dashboard AS
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
        CREATE TABLE temp_vhnd_form AS 
            SELECT DISTINCT awc_id as awc_id,
                 FIRST_VALUE(vhsnd_date_past_month) over w as vhsnd_date_past_month,
                 FIRST_VALUE(anm_mpw=1) over w as anm_mpw_present,
                 FIRST_VALUE(asha_present=1) over w as asha_present,
                 FIRST_VALUE(child_immu=1) over w as child_immu,
                 FIRST_VALUE(anc_today=1) over w as anc_today,
                %(start_date)s::DATE AS month
            FROM "{ucr_tablename}" WHERE
        vhsnd_date_past_month >= %(start_date)s AND
        vhsnd_date_past_month < %(end_date)s WINDOW w AS(
            PARTITION BY awc_id
            ORDER BY vhsnd_date_past_month RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )ORDER BY awc_id, month;""".format(
            ucr_tablename=self.ucr_tablename
        ), {
            'start_date': self.month,
            'end_date': self.month + relativedelta(months=1)
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
            total_3_6_male_benefit_in_month = ut.valid_reg_in_month_3_6_male,
            total_3_6_female_reg_in_month = ut.open_reg_in_month_3_6_female,
            total_3_6_male_reg_in_month = ut.open_reg_in_month_3_6_male
        FROM temp_gov_dashboard ut
        WHERE agg_gov.awc_id = ut.awc_id;
        """.format(
            tmp_tablename=self.staging_tablename,
        ), {}

        yield """
        UPDATE "{tmp_tablename}" agg_gov
        SET vhsnd_date_past_month = ut.vhsnd_date_past_month,
            anm_mpw_present = ut.anm_mpw_present,
            asha_present = ut.asha_present,
            child_immu = ut.child_immu,
            anc_today = ut.anc_today
        FROM temp_vhnd_form ut
        WHERE agg_gov.awc_id = ut.awc_id;
        """.format(
            tmp_tablename=self.staging_tablename,
        ), {}

        yield """
        DROP TABLE temp_gov_dashboard;
        DROP TABLE temp_vhnd_form;
        """, {}

    def indexes(self):
        return []
