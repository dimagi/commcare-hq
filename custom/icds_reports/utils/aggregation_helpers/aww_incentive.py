from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name

from custom.icds_reports.const import AWW_INCENTIVE_TABLE
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, month_formatter


class AwwIncentiveAggregationHelper(BaseICDSAggregationHelper):
    aggregate_parent_table = AWW_INCENTIVE_TABLE
    aggregate_child_table_prefix = 'icds_db_aww_incentive_'

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
            state_id, month, awc_id, block_id, state_name, district_name, block_name, 
            supervisor_name, awc_name, aww_name, contact_phone_number, wer_weighed,
            wer_eligible, awc_num_open, valid_visits, expected_visits
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            awcm.awc_id,
            awcm.block_id,
            awcm.state_name,
            awcm.district_name,
            awcm.block_name,
            awcm.supervisor_name,
            awcm.awc_name,
            awcm.aww_name,
            awcm.contact_phone_number,
            awcm.wer_weighed,
            awcm.wer_eligible,
            awcm.awc_days_open,
            sum(ccsm.valid_visits),
            sum(ccsm.expected_visits)
          FROM agg_awc_monthly as awcm
          INNER JOIN agg_ccs_record_monthly AS ccsm
          ON ccsm.month=awcm.month AND ccsm.awc_id=awcm.awc_id AND ccsm.aggregation_level=awcm.aggregation_level
          WHERE awcm.month = %(month)s AND awcm.state_id = %(state_id)s and awcm.aggregation_level=5
          GROUP BY awcm.awc_id, awcm.block_id, awcm.state_name, awcm.district_name,
                   awcm.block_name, awcm.supervisor_name, awcm.awc_name, awcm.aww_name,
                   awcm.contact_phone_number, awcm.wer_weighed, awcm.wer_eligible,
                   awcm.awc_days_open
        );
        /* update expected visits for cf cases (not in agg_ccs_record */
        UPDATE "{tablename}" perf
        SET expected_visits = expected_visits + ucr.expected
        FROM (
             SELECT FLOOR(SUM(0.39)) AS expected, awc_id
             FROM "{ccs_record_case_ucr}"
             WHERE %(month)s - add > 183 AND (closed_on IS NULL OR date_trunc('month', closed_on)::DATE > %(month)s) AND date_trunc('month', opened_on) <= %(month)s
             GROUP BY awc_id
             ) ucr
        WHERE ucr.awc_id = perf.awc_id
        """.format(
            tablename=tablename,
            ccs_record_case_ucr=self.ccs_record_case_ucr_tablename
        ), query_params
