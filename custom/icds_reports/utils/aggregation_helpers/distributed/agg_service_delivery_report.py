from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AGG_SDR_TABLE
from custom.icds_reports.utils.aggregation_helpers import  month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import AggregationPartitionedHelper


class AggServiceDeliveryReportHelper(AggregationPartitionedHelper):
    helper_key = 'agg-service_delivery_report'
    base_tablename = AGG_SDR_TABLE
    staging_tablename = 'staging_{}'.format(AGG_SDR_TABLE)

    @property
    def monthly_tablename(self):
        return "{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"))

    @property
    def previous_agg_table_name(self):
        return f"previous_{self.monthly_tablename}"

    @property
    def model(self):
        from custom.icds_reports.models.aggregate import AggServiceDeliveryReport
        return AggServiceDeliveryReport

    def update_queries(self):
        columns = (
            ('state_id', 'awc_location_local.state_id'),
            ('district_id', 'awc_location_local.district_id'),
            ('block_id', 'awc_location_local.block_id'),
            ('supervisor_id', 'awc_location_local.supervisor_id'),
            ('awc_id', 'awc_location_local.doc_id'),
            ('month', "'{}'".format(month_formatter(self.month))),
            ('aggregation_level', '5'),
            ('state_is_test','awc_location_local.state_is_test'),
            ('district_is_test','awc_location_local.district_is_test'),
            ('block_is_test','awc_location_local.block_is_test'),
            ('supervisor_is_test','awc_location_local.supervisor_is_test'),
            ('awc_is_test','awc_location_local.awc_is_test'),

        )
        yield """
                INSERT INTO "{tmp_tablename}" (
                    {columns}
                )
                (
                SELECT
                {calculations}
                from awc_location_local 
                WHERE awc_location_local.aggregation_level=5 AND awc_location_local.state_is_test<>1);
                """.format(
            tmp_tablename=self.staging_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns])

        ), {
            'start_date': self.month
        }


        yield """
        CREATE TABLE temp_child_table AS
        SELECT
            supervisor_id,
            awc_id,
            SUM(pse_eligible) as pse_eligible,
            SUM(CASE WHEN pse_eligible=1 AND pse_days_attended=0 THEN 1 ELSE 0 END) as pse_0_days,
            SUM(CASE WHEN pse_eligible=1 AND pse_days_attended BETWEEN 1 AND 7 THEN 1 ELSE 0 END) as pse_1_7_days,
            SUM(CASE WHEN pse_eligible=1 AND pse_days_attended BETWEEN 8 AND 14 THEN 1 ELSE 0 END) as pse_8_14_days,
            SUM(CASE WHEN pse_eligible=1 AND pse_days_attended BETWEEN 15 AND 20 THEN 1 ELSE 0 END) as pse_15_20_days,
            SUM(CASE WHEN pse_eligible=1 AND pse_days_attended>=21 THEN 1 ELSE 0 END) as pse_21_days,
            
            SUM(CASE WHEN pse_eligible=1 AND lunch_count=0 THEN 1 ELSE 0 END) as lunch_0_days,
            SUM(CASE WHEN pse_eligible=1 AND lunch_count BETWEEN 1 AND 7 THEN 1 ELSE 0 END) as lunch_1_7_days,
            SUM(CASE WHEN pse_eligible=1 AND lunch_count BETWEEN 8 AND 14 THEN 1 ELSE 0 END) as lunch_8_14_days,
            SUM(CASE WHEN pse_eligible=1 AND lunch_count BETWEEN 15 AND 20 THEN 1 ELSE 0 END) as lunch_15_20_days,
            SUM(CASE WHEN pse_eligible=1 AND lunch_count>=21 THEN 1 ELSE 0 END) as lunch_21_days,
            
            SUM(thr_eligible) as thr_eligible,
            SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed=0 THEN 1 ELSE 0 END) as thr_0_days,
            SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 1 AND 7 THEN 1 ELSE 0 END) as thr_1_7_days,
            SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 8 AND 14 THEN 1 ELSE 0 END) as thr_8_14_days,
            SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 15 AND 20 THEN 1 ELSE 0 END) as thr_15_20_days,
            SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed>=21 THEN 1 ELSE 0 END) as thr_21_days
        FROM child_health_monthly
        WHERE month=%(start_date)s
        GROUP BY supervisor_id, awc_id
            
        """, {
            "start_date":self.month
        }


        yield """
        UPDATE "{tmp_tablename}" agg_sdr
        SET pse_eligible = ut.pse_eligible,
            pse_0_days = ut.pse_0_days,
            pse_1_7_days = ut.pse_1_7_days,
            pse_8_14_days = ut.pse_8_14_days,
            pse_15_20_days = ut.pse_15_20_days,
            pse_21_days = ut.pse_21_days,
            lunch_eligible = ut.pse_eligible,
            lunch_0_days = ut.lunch_0_days,
            lunch_1_7_days = ut.lunch_1_7_days,
            lunch_8_14_days = ut.lunch_8_14_days,
            lunch_15_20_days = ut.lunch_15_20_days,
            lunch_21_days = ut.lunch_21_days,
            thr_eligible = ut.thr_eligible,
            thr_0_days = ut.thr_0_days,
            thr_1_7_days = ut.thr_1_7_days,
            thr_8_14_days = ut.thr_8_14_days,
            thr_15_20_days = ut.thr_15_20_days,
            thr_21_days = ut.thr_21_days
        FROM temp_child_table ut
        WHERE agg_sdr.awc_id = ut.awc_id;
        """.format(
            tmp_tablename=self.staging_tablename,
        ), {}

        yield """
        DROP TABLE temp_child_table;
        
        """, {}

        yield """
        CREATE TABLE temp_ccs_table AS
            SELECT
                supervisor_id,
                awc_id,
                SUM(thr_eligible) as mother_thr_eligible,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed=0 THEN 1 ELSE 0 END) as mother_thr_0_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 1 AND 7 THEN 1 ELSE 0 END) as mother_thr_1_7_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 8 AND 14 THEN 1 ELSE 0 END) as mother_thr_8_14_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 15 AND 20 THEN 1 ELSE 0 END) as mother_thr_15_20_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed>=21 THEN 1 ELSE 0 END) as mother_thr_21_days
            FROM ccs_record_monthly
            WHERE month=%(start_date)s
            GROUP BY supervisor_id, awc_id
        """,{
            "start_date":self.month
        }

        yield """
        UPDATE "{tmp_tablename}" agg_sdr
        SET thr_eligible = thr_eligible +  ut.mother_thr_eligible,
            thr_0_days = thr_0_days +  ut.mother_thr_0_days,
            thr_1_7_days = thr_1_7_days +  ut.mother_thr_1_7_days,
            thr_8_14_days = thr_8_14_days +  ut.mother_thr_8_14_days,
            thr_15_20_days = thr_15_20_days +  ut.mother_thr_15_20_days,
            thr_21_days = thr_21_days +  ut.mother_thr_21_days
        FROM temp_ccs_table ut
        WHERE agg_sdr.awc_id = ut.awc_id;
        """.format(
            tmp_tablename=self.staging_tablename,
        ), {}

        yield """
        DROP TABLE temp_ccs_table;
        """, {}

    def rollup_query(self, aggregation_level):
        columns = (
            ('state_id', 'state_id'),
            ('district_id', lambda col: col if aggregation_level > 1 else "'All'"),
            ('block_id', lambda col: col if aggregation_level > 2 else "'All'"),
            ('supervisor_id', lambda col: col if aggregation_level > 3 else "'All'"),
            ('awc_id', lambda col: col if aggregation_level > 4 else "'All'"),
            ('aggregation_level', str(aggregation_level)),
            ('month', 'month'),
            ('pse_eligible',),
            ('pse_0_days',),
            ('pse_1_7_days',),
            ('pse_8_14_days',),
            ('pse_15_20_days',),
            ('pse_21_days',),
            ('thr_eligible',),
            ('thr_0_days',),
            ('thr_1_7_days',),
            ('thr_8_14_days',),
            ('thr_15_20_days',),
            ('thr_21_days',),
            ('lunch_eligible',),
            ('lunch_0_days',),
            ('lunch_1_7_days',),
            ('lunch_8_14_days',),
            ('lunch_15_20_days',),
            ('lunch_21_days',),
            ('state_is_test', 'MAX(state_is_test)'),
            (
                'district_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 1 else "0"
            ),
            (
                'block_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 2 else "0"
            ),
            (
                'supervisor_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 3 else "0"
            ),
            (
                'awc_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 4 else "0"
            )
        )
        def _transform_column(column_tuple):
            column = column_tuple[0]

            if len(column_tuple) == 2:
                agg_col = column_tuple[1]
                if isinstance(agg_col, str):
                    return column_tuple
                elif callable(agg_col):
                    return (column, agg_col(column))
            return (column, 'SUM({})'.format(column))

        columns = list(map(_transform_column, columns))

        group_by = ["state_id"]
        child_location = 'district_is_test'
        if aggregation_level > 1:
            group_by.append("district_id")
            child_location = 'block_is_test'
        if aggregation_level > 2:
            group_by.append("block_id")
            child_location = 'supervisor_is_test'
        if aggregation_level > 3:
            group_by.append("supervisor_id")
            child_location = 'awc_is_test'

        group_by.append('month')
        group_by = ", ".join(group_by)
        column_names = ", ".join([col[0] for col in columns])
        calculations = ", ".join([col[1] for col in columns])

        return f"""
        INSERT INTO "{self.staging_tablename}" (
            {column_names}
        ) (
            SELECT {calculations}
            FROM "{self.staging_tablename}"
            WHERE {child_location} = 0 AND aggregation_level = {aggregation_level + 1}
            GROUP BY {group_by}
            ORDER BY {group_by}
        )
        """

    def indexes(self):
        staging_tablename = self.staging_tablename
        return [
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, state_id)',
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, district_id) WHERE aggregation_level > 1',
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, block_id) WHERE aggregation_level > 2',
            f'CREATE INDEX ON "{staging_tablename}" (aggregation_level, supervisor_id) WHERE aggregation_level > 3',
        ]
