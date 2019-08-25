
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import (
    AWW_INCENTIVE_TABLE,
    AGG_CCS_RECORD_CF_TABLE
)
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper


class AwwIncentiveAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'awc-incentive'
    aggregate_parent_table = AWW_INCENTIVE_TABLE
    aggregate_child_table_prefix = 'icds_db_aww_incentive_'

    def aggregate(self, cursor):
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(self.drop_table_query())
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_params)

    @property
    def ccs_record_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-ccs_record_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }

        return """
        INSERT INTO "{tablename}" (
            state_id, district_id, month, awc_id, block_id, supervisor_id, state_name, district_name, block_name,
            supervisor_name, awc_name, aww_name, contact_phone_number, wer_weighed,
            wer_eligible, awc_num_open, valid_visits, expected_visits, is_launched,
            visit_denominator, awh_eligible, incentive_eligible
        ) (
          SELECT
            %(state_id)s AS state_id,
            awcm.district_id,
            %(month)s AS month,
            awcm.awc_id,
            awcm.block_id,
            awcm.supervisor_id,
            awcm.state_name,
            awcm.district_name,
            awcm.block_name,
            awcm.supervisor_name,
            awcm.awc_name,
            awcm.aww_name,
            awcm.contact_phone_number,
            awcm.wer_weighed_0_2,
            awcm.wer_eligible_0_2,
            awcm.awc_days_open,
            sum(ccsm.valid_visits),
            sum(ccsm.expected_visits),
            awcm.is_launched = 'yes',
            round(sum(ccsm.expected_visits)),
            awcm.awc_days_open >= 21,
            (ROUND(awcm.wer_weighed_0_2 / GREATEST(awcm.wer_eligible_0_2, 1)::NUMERIC, 4) >= 0.6
                    OR COALESCE(awcm.wer_eligible_0_2, 0) = 0)
                AND (ROUND(sum(ccsm.valid_visits) / GREATEST(round(sum(ccsm.expected_visits)), 1)::NUMERIC, 4) >= 0.6
                    OR round(COALESCE(sum(ccsm.expected_visits), 0)) = 0)
          FROM agg_awc_monthly as awcm
          INNER JOIN agg_ccs_record_monthly AS ccsm
          ON ccsm.month=awcm.month AND ccsm.awc_id=awcm.awc_id AND ccsm.aggregation_level=awcm.aggregation_level
          WHERE awcm.month = %(month)s AND awcm.state_id = %(state_id)s and awcm.aggregation_level=5
          GROUP BY awcm.awc_id, awcm.block_id, awcm.supervisor_id, awcm.district_id, awcm.state_name,
                awcm.district_name, awcm.block_name, awcm.supervisor_name, awcm.awc_name, awcm.aww_name,
                awcm.contact_phone_number, awcm.wer_weighed_0_2, awcm.wer_eligible_0_2,
                awcm.awc_days_open, awcm.is_launched
        );
        /* update visits for cf cases (not in agg_ccs_record) */
        CREATE TEMPORARY TABLE "tmp_ccs_cf" AS SELECT
            SUM(0.39) AS expected,
            SUM(COALESCE(agg_cf.valid_visits, 0)) as valid,
            ucr.awc_id
            FROM "{ccs_record_case_ucr}" ucr
            LEFT OUTER JOIN "{agg_cf_table}" agg_cf ON ucr.doc_id = agg_cf.case_id
                AND agg_cf.month = %(month)s AND agg_cf.supervisor_id = ucr.supervisor_id
            WHERE %(month)s - add BETWEEN 184 AND 548
                AND (
                    closed_on IS NULL OR date_trunc('month', closed_on)::DATE > %(month)s
                )
                AND date_trunc('month', opened_on) <= %(month)s
            GROUP BY ucr.awc_id, ucr.supervisor_id;
        UPDATE "{tablename}" perf
        SET expected_visits = expected_visits + cf_data.expected,
            valid_visits = valid_visits + cf_data.valid,
            visit_denominator = round(expected_visits + cf_data.expected),
            incentive_eligible = (ROUND(wer_weighed / GREATEST(wer_eligible, 1)::NUMERIC, 4) >= 0.6 
                                  OR COALESCE(wer_eligible, 0) = 0)
                                 AND (ROUND((valid_visits + cf_data.valid) / GREATEST(round(expected_visits + cf_data.expected), 1)::NUMERIC, 4) >= 0.6
                                  OR round(COALESCE((expected_visits + cf_data.expected), 0)) = 0)
        FROM "tmp_ccs_cf" cf_data
        WHERE cf_data.awc_id = perf.awc_id;
        DROP TABLE "tmp_ccs_cf";
        """.format(
            tablename=tablename,
            ccs_record_case_ucr=self.ccs_record_case_ucr_tablename,
            agg_cf_table=AGG_CCS_RECORD_CF_TABLE,
        ), query_params
