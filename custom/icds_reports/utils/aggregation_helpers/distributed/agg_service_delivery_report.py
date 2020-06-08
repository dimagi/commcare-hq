from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AGG_SDR_TABLE
from custom.icds_reports.utils.aggregation_helpers import  month_formatter, get_child_health_temp_tablename
from custom.icds_reports.utils.aggregation_helpers.distributed.base import AggregationPartitionedHelper


class AggServiceDeliveryReportHelper(AggregationPartitionedHelper):
    helper_key = 'agg-service_delivery_report'
    base_tablename = AGG_SDR_TABLE
    staging_tablename = f'staging_{AGG_SDR_TABLE}'

    @property
    def monthly_tablename(self):
        month_start = self.month.strftime("%Y-%m-%d")
        return f"{self.base_tablename}_{month_start}"

    @property
    def previous_agg_table_name(self):
        return f"previous_{self.monthly_tablename}"

    @property
    def model(self):
        from custom.icds_reports.models.aggregate import AggServiceDeliveryReport
        return AggServiceDeliveryReport

    @property
    def child_temp_tablename(self):
        return get_child_health_temp_tablename(self.month)

    @property
    def temporary_tablename(self):
        return f"temp_{self.monthly_tablename}"

    def create_temporary_table(self):
        return f"""
        CREATE UNLOGGED TABLE \"{self.temporary_tablename}\" (LIKE {self.base_tablename} INCLUDING INDEXES);
        SELECT create_distributed_table('{self.temporary_tablename}', 'supervisor_id');
        """

    @property
    def cbe_ucr_table(self):
        return get_table_name(self.domain, 'static-cbe_form')

    def drop_temporary_table(self):
        return f"""DROP TABLE IF EXISTS \"{self.temporary_tablename}\";"""

    def staging_queries(self):
        month_start_string = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))
        columns = (
            ('state_id', 'awc_location.state_id'),
            ('district_id', 'awc_location.district_id'),
            ('block_id', 'awc_location.block_id'),
            ('supervisor_id', 'awc_location.supervisor_id'),
            ('awc_id', 'awc_location.doc_id'),
            ('month', f"'{month_start_string}'"),
            ('aggregation_level', '5'),
            ('state_is_test','awc_location.state_is_test'),
            ('district_is_test','awc_location.district_is_test'),
            ('block_is_test','awc_location.block_is_test'),
            ('supervisor_is_test','awc_location.supervisor_is_test'),
            ('awc_is_test','awc_location.awc_is_test')
        )

        column_names = ", ".join([col[0] for col in columns])
        calculations = ", ".join([col[1] for col in columns])

        yield f"""
                INSERT INTO "{self.temporary_tablename}" (
                    {column_names}
                )
                (
                SELECT
                {calculations}
                from awc_location
                WHERE awc_location.aggregation_level=5);
                """,{
        }

        yield f"""
        UPDATE "{self.temporary_tablename}" agg_sdr
        SET
            pse_eligible = ut.pse_eligible,
            pse_0_days = ut.pse_0_days,
            pse_1_7_days = ut.pse_1_7_days,
            pse_8_14_days = ut.pse_8_14_days,
            pse_15_20_days = ut.pse_15_20_days,
            pse_21_days = ut.pse_21_days,
            pse_21_24_days = ut.pse_21_24_days,
            pse_25_days = ut.pse_25_days,
            lunch_eligible = ut.pse_eligible,
            lunch_0_days = ut.lunch_0_days,
            lunch_1_7_days = ut.lunch_1_7_days,
            lunch_8_14_days = ut.lunch_8_14_days,
            lunch_15_20_days = ut.lunch_15_20_days,
            lunch_21_days = ut.lunch_21_days,
            lunch_21_24_days = ut.lunch_21_24_days,
            lunch_25_days = ut.lunch_25_days,
            thr_eligible = ut.thr_eligible,
            thr_0_days = ut.thr_0_days,
            thr_1_7_days = ut.thr_1_7_days,
            thr_8_14_days = ut.thr_8_14_days,
            thr_15_20_days = ut.thr_15_20_days,
            thr_21_days = ut.thr_21_days,
            thr_21_24_days = ut.thr_21_24_days,
            thr_25_days = ut.thr_25_days,
            child_thr_eligible = ut.thr_eligible,
            child_thr_0_days = ut.thr_0_days,
            child_thr_1_7_days = ut.thr_1_7_days,
            child_thr_8_14_days = ut.thr_8_14_days,
            child_thr_15_20_days = ut.thr_15_20_days,
            child_thr_21_days = ut.thr_21_days,
            child_thr_21_24_days = ut.thr_21_24_days,
            child_thr_25_days = ut.thr_25_days,
            children_0_3 = ut.children_0_3,
            children_3_5 = ut.children_3_5,
            gm_0_3 = ut.gm_0_3,
            gm_3_5 = ut.gm_3_5
        FROM (
            SELECT
                supervisor_id,
                awc_id,
                month,
                SUM(pse_eligible) as pse_eligible,
                SUM(CASE WHEN pse_eligible=1 AND pse_days_attended=0 THEN 1 ELSE 0 END) as pse_0_days,
                SUM(CASE WHEN pse_eligible=1 AND
                    pse_days_attended BETWEEN 1 AND 7 THEN 1 ELSE 0 END) as pse_1_7_days,
                SUM(CASE WHEN pse_eligible=1 AND
                    pse_days_attended BETWEEN 8 AND 14 THEN 1 ELSE 0 END) as pse_8_14_days,
                SUM(CASE WHEN pse_eligible=1 AND
                    pse_days_attended BETWEEN 15 AND 20 THEN 1 ELSE 0 END) as pse_15_20_days,
                SUM(CASE WHEN pse_eligible=1 AND pse_days_attended>=21 THEN 1 ELSE 0 END) as pse_21_days,
                SUM(CASE WHEN pse_eligible=1 AND pse_days_attended BETWEEN 21 AND 24 THEN 1 ELSE 0 END) as pse_21_24_days,
                SUM(CASE WHEN pse_eligible=1 AND pse_days_attended>=25 THEN 1 ELSE 0 END) as pse_25_days,

                SUM(CASE WHEN pse_eligible=1 AND lunch_count=0 THEN 1 ELSE 0 END) as lunch_0_days,
                SUM(CASE WHEN pse_eligible=1 AND lunch_count BETWEEN 1 AND 7 THEN 1 ELSE 0 END) as lunch_1_7_days,
                SUM(CASE WHEN pse_eligible=1 AND lunch_count BETWEEN 8 AND 14 THEN 1 ELSE 0 END) as lunch_8_14_days,
                SUM(CASE WHEN pse_eligible=1 AND lunch_count BETWEEN 15 AND 20 THEN 1 ELSE 0 END) as lunch_15_20_days,
                SUM(CASE WHEN pse_eligible=1 AND lunch_count>=21 THEN 1 ELSE 0 END) as lunch_21_days,
                SUM(CASE WHEN pse_eligible=1 AND lunch_count BETWEEN 21 AND 24 THEN 1 ELSE 0 END) as lunch_21_24_days,
                SUM(CASE WHEN pse_eligible=1 AND lunch_count>=25 THEN 1 ELSE 0 END) as lunch_25_days,

                SUM(thr_eligible) as thr_eligible,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed=0 THEN 1 ELSE 0 END) as thr_0_days,
                SUM(CASE WHEN thr_eligible=1 AND
                    num_rations_distributed BETWEEN 1 AND 7 THEN 1 ELSE 0 END) as thr_1_7_days,
                SUM(CASE WHEN thr_eligible=1 AND
                    num_rations_distributed BETWEEN 8 AND 14 THEN 1 ELSE 0 END) as thr_8_14_days,
                SUM(CASE WHEN thr_eligible=1 AND
                    num_rations_distributed BETWEEN 15 AND 20 THEN 1 ELSE 0 END) as thr_15_20_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed>=21 THEN 1 ELSE 0 END) as thr_21_days,

                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 21 AND 24 THEN 1 ELSE 0 END) as thr_21_24_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed>=25 THEN 1 ELSE 0 END) as thr_25_days,

                SUM(CASE WHEN age_tranche::integer <=36 THEN valid_in_month ELSE 0 END ) as children_0_3,
                SUM(CASE WHEN age_tranche::integer BETWEEN 37 AND 60
                    THEN valid_in_month ELSE 0 END ) as children_3_5,
                SUM(CASE WHEN age_tranche::integer <=36 THEN nutrition_status_weighed ELSE 0 END) as gm_0_3,
                SUM(CASE WHEN age_tranche::integer BETWEEN 37 AND 60
                    THEN nutrition_status_weighed ELSE 0 END)AS gm_3_5
            FROM "{self.child_temp_tablename}"
            WHERE month=%(start_date)s
            GROUP BY supervisor_id, awc_id, month
            ) ut
        WHERE (
            agg_sdr.awc_id=ut.awc_id AND
            agg_sdr.aggregation_level=5 AND
            agg_sdr.month=ut.month
        )
        """, {
            "start_date":self.month
        }

        yield f"""
        UPDATE "{self.temporary_tablename}" agg_sdr
        SET
            thr_eligible = COALESCE(thr_eligible, 0) +  ut.mother_thr_eligible,
            thr_0_days = COALESCE(thr_0_days, 0) +  ut.mother_thr_0_days,
            thr_1_7_days = COALESCE(thr_1_7_days, 0) +  ut.mother_thr_1_7_days,
            thr_8_14_days = COALESCE(thr_8_14_days, 0) +  ut.mother_thr_8_14_days,
            thr_15_20_days = COALESCE(thr_15_20_days, 0) +  ut.mother_thr_15_20_days,
            thr_21_days = COALESCE(thr_21_days, 0) +  ut.mother_thr_21_days,
            thr_21_24_days = COALESCE(thr_21_24_days, 0) + ut.mother_thr_21_24_days,
            thr_25_days = COALESCE(thr_25_days, 0) +  ut.mother_thr_25_days,
            pw_thr_eligible = ut.pw_thr_eligible,
            pw_thr_0_days = ut.pw_thr_0_days,
            pw_thr_1_7_days = ut.pw_thr_1_7_days,
            pw_thr_8_14_days = ut.pw_thr_8_14_days,
            pw_thr_15_20_days = ut.pw_thr_15_20_days,
            pw_thr_21_days = ut.pw_thr_21_days,
            pw_thr_21_24_days = ut.pw_thr_21_24_days,
            pw_thr_25_days = ut.pw_thr_25_days,
            lw_thr_eligible = ut.lw_thr_eligible,
            lw_thr_0_days = ut.lw_thr_0_days,
            lw_thr_1_7_days = ut.lw_thr_1_7_days,
            lw_thr_8_14_days = ut.lw_thr_8_14_days,
            lw_thr_15_20_days = ut.lw_thr_15_20_days,
            lw_thr_21_days = ut.lw_thr_21_days,
            lw_thr_21_24_days = ut.lw_thr_21_24_days,
            lw_thr_25_days = ut.lw_thr_25_days

        FROM (
            SELECT
                supervisor_id,
                awc_id,
                month,
                SUM(thr_eligible) as mother_thr_eligible,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed=0 THEN 1 ELSE 0 END) as mother_thr_0_days,

                SUM(CASE WHEN pregnant=1 THEN thr_eligible ELSE 0 END) as pw_thr_eligible,
                SUM(CASE WHEN thr_eligible=1 AND pregnant=1 AND num_rations_distributed=0
                    THEN 1 ELSE 0 END) as pw_thr_0_days,
                SUM(CASE WHEN thr_eligible=1 AND pregnant=1 AND num_rations_distributed BETWEEN 1 AND 7
                    THEN 1 ELSE 0 END) as pw_thr_1_7_days,
                SUM(CASE WHEN thr_eligible=1 AND pregnant=1 AND num_rations_distributed BETWEEN 8 AND 14
                    THEN 1 ELSE 0 END) as pw_thr_8_14_days,
                SUM(CASE WHEN thr_eligible=1 AND pregnant=1 AND num_rations_distributed BETWEEN 15 AND 20
                    THEN 1 ELSE 0 END) as pw_thr_15_20_days,
                SUM(CASE WHEN thr_eligible=1 AND pregnant=1 AND num_rations_distributed>=21
                    THEN 1 ELSE 0 END) as pw_thr_21_days,
                SUM(CASE WHEN thr_eligible=1 AND pregnant=1 AND num_rations_distributed BETWEEN 21 AND 24
                    THEN 1 ELSE 0 END) as pw_thr_21_24_days,
                SUM(CASE WHEN thr_eligible=1 AND pregnant=1 AND num_rations_distributed>=25
                    THEN 1 ELSE 0 END) as pw_thr_25_days,
                SUM(CASE WHEN lactating=1 THEN thr_eligible ELSE 0 END) as lw_thr_eligible,
                SUM(CASE WHEN thr_eligible=1 AND lactating=1 AND num_rations_distributed=0
                    THEN 1 ELSE 0 END) as lw_thr_0_days,
                SUM(CASE WHEN thr_eligible=1 AND lactating=1 AND num_rations_distributed BETWEEN 1 AND 7
                    THEN 1 ELSE 0 END) as lw_thr_1_7_days,
                SUM(CASE WHEN thr_eligible=1 AND lactating=1 AND num_rations_distributed BETWEEN 8 AND 14
                    THEN 1 ELSE 0 END) as lw_thr_8_14_days,
                SUM(CASE WHEN thr_eligible=1 AND lactating=1 AND num_rations_distributed BETWEEN 15 AND 20
                    THEN 1 ELSE 0 END) as lw_thr_15_20_days,
                SUM(CASE WHEN thr_eligible=1 AND lactating=1 AND num_rations_distributed>=21
                    THEN 1 ELSE 0 END) as lw_thr_21_days,
                SUM(CASE WHEN thr_eligible=1 AND lactating=1 AND num_rations_distributed BETWEEN 21 AND 24
                    THEN 1 ELSE 0 END) as lw_thr_21_24_days,
                SUM(CASE WHEN thr_eligible=1 AND lactating=1 AND num_rations_distributed>=25
                    THEN 1 ELSE 0 END) as lw_thr_25_days,

                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 1 AND 7 THEN 1 ELSE 0 END) as mother_thr_1_7_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 8 AND 14 THEN 1 ELSE 0 END) as mother_thr_8_14_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 15 AND 20 THEN 1 ELSE 0 END) as mother_thr_15_20_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed>=21 THEN 1 ELSE 0 END) as mother_thr_21_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed BETWEEN 21 AND 24 THEN 1 ELSE 0 END) as mother_thr_21_24_days,
                SUM(CASE WHEN thr_eligible=1 AND num_rations_distributed>=25 THEN 1 ELSE 0 END) as mother_thr_25_days
            FROM ccs_record_monthly
            WHERE month=%(start_date)s
            GROUP BY supervisor_id, awc_id, month
        ) ut
        WHERE (
            agg_sdr.awc_id=ut.awc_id AND
            agg_sdr.aggregation_level=5 AND
            agg_sdr.month=ut.month
        )
        """,{
            "start_date": self.month
        }

        yield f"""
        UPDATE "{self.temporary_tablename}" agg_sdr
        SET
            third_fourth_month_of_pregnancy_count = ut.third_fourth_month_of_pregnancy_count,
            annaprasan_diwas_count = ut.annaprasan_diwas_count,
            suposhan_diwas_count = ut.suposhan_diwas_count,
            coming_of_age_count = ut.coming_of_age_count,
            public_health_message_count = ut.public_health_message_count
        FROM (
            SELECT
                awc_id,
                SUM(CASE WHEN theme_cbe='third_fourth_month_of_pregnancy' THEN 1 ELSE 0 END) as third_fourth_month_of_pregnancy_count,
                SUM(CASE WHEN theme_cbe='annaprasan_diwas' THEN 1 ELSE 0 END) as annaprasan_diwas_count,
                SUM(CASE WHEN theme_cbe='suposhan_diwas' THEN 1 ELSE 0 END) as suposhan_diwas_count,
                SUM(CASE WHEN theme_cbe='coming_of_age' THEN 1 ELSE 0 END) as coming_of_age_count,
                SUM(CASE WHEN theme_cbe='public_health_message' THEN 1 ELSE 0 END) as public_health_message_count
            FROM "{self.cbe_ucr_table}" ucr
            WHERE ucr.date_cbe_organise>=%(start_date)s AND ucr.date_cbe_organise<%(next_month_start_date)s
            GROUP BY awc_id
            ) ut WHERE ut.awc_id = agg_sdr.awc_id
        """, {
            'start_date': self.month,
            'next_month_start_date': next_month_start
        }

    def update_queries(self):

        yield f"""
            DROP TABLE IF EXISTS "local_tmp_agg_sdr";
            """, {
        }

        yield f"""
            CREATE TABLE "local_tmp_agg_sdr" AS SELECT * FROM "{self.temporary_tablename}";
            """, {
        }

        yield f"""
            INSERT INTO "{self.staging_tablename}" SELECT * from "local_tmp_agg_sdr";
            """, {
        }
        yield f"""
            DROP TABLE "local_tmp_agg_sdr";
            """, {
        }

    def rollup_query(self, aggregation_level):
        from custom.icds_reports.utils import (
            create_group_by, test_column_name,
            prepare_rollup_query, column_value_as_per_agg_level
        )
        columns = (
            ('state_id', 'state_id'),
            ('district_id', column_value_as_per_agg_level(aggregation_level, 1,'district_id', "'All'") ),
            ('block_id', column_value_as_per_agg_level(aggregation_level, 2,'block_id', "'All'")),
            ('supervisor_id', column_value_as_per_agg_level(aggregation_level, 3,'supervisor_id', "'All'")),
            ('awc_id', column_value_as_per_agg_level(aggregation_level, 4,'awc_id', "'All'")),
            ('aggregation_level', str(aggregation_level)),
            ('month', 'month'),
            ('pse_eligible',),
            ('pse_0_days',),
            ('pse_1_7_days',),
            ('pse_8_14_days',),
            ('pse_15_20_days',),
            ('pse_21_days',),
            ('pse_21_24_days',),
            ('pse_25_days',),
            ('thr_eligible',),
            ('thr_0_days',),
            ('thr_1_7_days',),
            ('thr_8_14_days',),
            ('thr_15_20_days',),
            ('thr_21_days',),
            ('thr_21_24_days',),
            ('thr_25_days',),
            ('lunch_eligible',),
            ('lunch_0_days',),
            ('lunch_1_7_days',),
            ('lunch_8_14_days',),
            ('lunch_15_20_days',),
            ('lunch_21_days',),
            ('lunch_21_24_days',),
            ('lunch_25_days',),
            ('children_0_3',),
            ('children_3_5',),
            ('gm_0_3',),
            ('gm_3_5',),
            ('third_fourth_month_of_pregnancy_count',),
            ('annaprasan_diwas_count',),
            ('suposhan_diwas_count',),
            ('coming_of_age_count',),
            ('public_health_message_count',),
            ('state_is_test', 'MAX(state_is_test)'),
            ('district_is_test', column_value_as_per_agg_level(aggregation_level, 1,'MAX(district_is_test)', "0")),
            ('block_is_test', column_value_as_per_agg_level(aggregation_level, 2,'MAX(block_is_test)', "0")),
            ('supervisor_is_test', column_value_as_per_agg_level(aggregation_level, 3,'MAX(supervisor_is_test)', "0")),
            ('awc_is_test', column_value_as_per_agg_level(aggregation_level, 3,'MAX(awc_is_test)', "0"))
        )

        column_names, calculations = prepare_rollup_query(columns)

        child_location_test_column_name = test_column_name(aggregation_level)

        group_by = create_group_by(aggregation_level)
        group_by.append('month')
        group_by_text = ", ".join(group_by)

        return f"""
        INSERT INTO "{self.staging_tablename}" (
            {column_names}
        ) (
            SELECT {calculations}
            FROM "{self.staging_tablename}"
            WHERE {child_location_test_column_name} = 0 AND aggregation_level = {aggregation_level + 1}
            GROUP BY {group_by_text}
            ORDER BY {group_by_text}
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
