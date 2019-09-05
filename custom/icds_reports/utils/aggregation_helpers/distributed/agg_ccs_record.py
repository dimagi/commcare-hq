from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper


class AggCcsRecordAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'agg-ccs-record'
    base_tablename = 'agg_ccs_record'

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    def aggregate(self, cursor):
        agg_query, agg_params = self.aggregation_query()
        update_queries = self.update_queries()
        rollup_queries = [self.rollup_query(i) for i in range(4, 0, -1)]
        index_queries = [self.indexes(i) for i in range(5, 0, -1)]
        index_queries = [query for index_list in index_queries for query in index_list]

        cursor.execute(self.drop_table_query())
        cursor.execute(agg_query, agg_params)
        for query, params in update_queries:
            cursor.execute(query, params)
        for query in rollup_queries:
            cursor.execute(query)
        for query in index_queries:
            cursor.execute(query)

    def _tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"), agg_level)

    @property
    def tablename(self):
        return self._tablename_func(5)

    def drop_table_query(self):
        return 'DELETE FROM "{}"'.format(self.tablename)

    def aggregation_query(self):

        columns = (
            ('state_id', 'awc_loc.state_id'),
            ('district_id', 'awc_loc.district_id'),
            ('block_id', 'awc_loc.block_id'),
            ('supervisor_id', 'awc_loc.supervisor_id'),
            ('awc_id', 'crm.awc_id'),
            ('month', 'crm.month'),
            ('ccs_status', 'crm.ccs_status'),
            ('trimester', "COALESCE(crm.trimester::text, '')", "coalesce_trimester"),
            ('caste', 'crm.caste'),
            ('disabled', "COALESCE(crm.disabled, 'no')", "coalesce_disabled"),
            ('minority', "COALESCE(crm.minority, 'no')", "coalesce_minority"),
            ('resident', "COALESCE(crm.resident,'no')", "coalesce_resident"),
            ('valid_in_month', 'sum(crm.valid_in_month)'),
            ('lactating', 'sum(crm.lactating)'),
            ('pregnant', 'sum(crm.pregnant)'),
            ('thr_eligible', 'sum(crm.thr_eligible)'),
            ('rations_21_plus_distributed', 'SUM(CASE WHEN crm.num_rations_distributed>=21 THEN 1 ELSE 0 END)'),
            ('tetanus_complete', 'sum(crm.tetanus_complete)'),
            ('delivered_in_month', 'sum(crm.delivered_in_month)'),
            ('anc1_received_at_delivery', 'sum(crm.anc1_received_at_delivery)'),
            ('anc2_received_at_delivery', 'sum(crm.anc2_received_at_delivery)'),
            ('anc3_received_at_delivery', 'sum(crm.anc3_received_at_delivery)'),
            ('anc4_received_at_delivery', 'sum(crm.anc4_received_at_delivery)'),
            ('registration_trimester_at_delivery', 'avg(crm.registration_trimester_at_delivery)'),
            ('using_ifa', 'sum(crm.using_ifa)'),
            ('ifa_consumed_last_seven_days', 'sum(crm.ifa_consumed_last_seven_days)'),
            ('anemic_normal', 'sum(crm.anemic_normal)'),
            ('anemic_moderate', 'sum(crm.anemic_moderate)'),
            ('anemic_severe', 'sum(crm.anemic_severe)'),
            ('anemic_unknown', 'sum(crm.anemic_unknown)'),
            ('extra_meal', 'sum(crm.extra_meal)'),
            ('resting_during_pregnancy', 'sum(crm.resting_during_pregnancy)'),
            ('bp1_complete', 'sum(crm.bp1_complete)'),
            ('bp2_complete', 'sum(crm.bp2_complete)'),
            ('bp3_complete', 'sum(crm.bp3_complete)'),
            ('pnc_complete', 'sum(crm.pnc_complete)'),
            ('trimester_2', 'sum(crm.trimester_2)'),
            ('trimester_3', 'sum(crm.trimester_3)'),
            ('postnatal', 'sum(crm.postnatal)'),
            ('counsel_bp_vid', 'sum(crm.counsel_bp_vid)'),
            ('counsel_preparation', 'sum(crm.counsel_preparation)'),
            ('counsel_immediate_bf', 'sum(crm.counsel_immediate_bf)'),
            ('counsel_fp_vid', 'sum(crm.counsel_fp_vid)'),
            ('counsel_immediate_conception', 'sum(crm.counsel_immediate_conception)'),
            ('counsel_accessible_postpartum_fp', 'sum(crm.counsel_accessible_postpartum_fp)'),
            ('has_aadhar_id', 'sum(crm.has_aadhar_id)'),
            ('aggregation_level', '5 '),
            ('valid_all_registered_in_month',
                'sum(CASE WHEN (crm.valid_in_month=1 AND crm.open_in_month=1 AND'
                ' (crm.pregnant_all=1 OR crm.lactating_all=1)) THEN 1 ELSE 0 END)'
             ),
            ('institutional_delivery_in_month', 'sum(crm.institutional_delivery_in_month)'),
            ('lactating_all', 'sum(crm.lactating_all)'),
            ('pregnant_all', 'sum(crm.pregnant_all)'),
            ('valid_visits', 'sum(crm.valid_visits)'),
            ('expected_visits', 'sum( '
             'CASE '
             'WHEN crm.pregnant=1 THEN 0.44 '
             'WHEN crm.month - crm.add <= 0 THEN 6 '
             'WHEN crm.month - crm.add < 182 THEN 1 '
             'ELSE 0.39 END'
             ')'),
        )
        query_cols = []
        for c in columns:
            if len(c) == 3:
                name = c[2]
            else:
                name = c[0]
            query_cols.append((name, c[1]))
        return """
        CREATE TEMPORARY TABLE "{tmp_tablename}" AS SELECT
            {query_cols}
            FROM  "{ccs_record_monthly_table}" as crm
            LEFT OUTER JOIN "awc_location" awc_loc ON awc_loc.doc_id = crm.awc_id
            WHERE crm.month = %(start_date)s AND awc_loc.state_id != '' AND awc_loc.state_id IS NOT NULL
            GROUP BY awc_loc.state_id, awc_loc.district_id, awc_loc.block_id, awc_loc.supervisor_id,
                crm.awc_id, crm.month, crm.ccs_status, coalesce_trimester, crm.caste,
                coalesce_disabled, coalesce_minority, coalesce_resident;
        INSERT INTO "{tablename}" ({final_columns}) SELECT * from "{tmp_tablename}";
        DROP TABLE "{tmp_tablename}";
        """.format(
            tablename=self.tablename,
            final_columns=", ".join([col[0] for col in columns]),
            query_cols=", ".join([
                '{} as {}'.format(expression, col_name) for col_name, expression in query_cols
            ]),
            ccs_record_monthly_table='ccs_record_monthly',
            tmp_tablename='tmp_{}'.format(self.tablename)
        ), {
            "start_date": self.month
        }

    def update_queries(self):
        yield """
        CREATE TEMPORARY TABLE "{tmp_tablename}" AS SELECT
            doc_id as awc_id,
            MAX(state_is_test) as state_is_test,
            MAX(district_is_test) as district_is_test,
            MAX(block_is_test) as block_is_test,
            MAX(supervisor_is_test) as supervisor_is_test,
            MAX(awc_is_test) as awc_is_test
            FROM "{awc_location_tablename}"
            GROUP BY awc_id;
        UPDATE "{tablename}" agg SET
              state_is_test = ut.state_is_test,
              district_is_test = ut.district_is_test,
              block_is_test = ut.block_is_test,
              supervisor_is_test = ut.supervisor_is_test,
              awc_is_test = ut.awc_is_test
            FROM (
              SELECT * FROM "{tmp_tablename}"
            ) ut
            WHERE ut.awc_id = agg.awc_id AND (
                (
                  agg.state_is_test IS NULL OR
                  agg.district_is_test IS NULL OR
                  agg.block_is_test IS NULL OR
                  agg.supervisor_is_test IS NULL OR
                  agg.awc_is_test IS NULL
                ) OR (
                  ut.state_is_test != agg.state_is_test OR
                  ut.district_is_test != agg.district_is_test OR
                  ut.block_is_test != agg.block_is_test OR
                  ut.supervisor_is_test != agg.supervisor_is_test OR
                  ut.awc_is_test != agg.awc_is_test
                )
            );
        """.format(
            tablename=self.tablename,
            tmp_tablename='tmp_{}'.format(self.tablename),
            awc_location_tablename='awc_location',
        ), {
        }

    def rollup_query(self, aggregation_level):
        columns = (
            ('state_id', 'state_id'),
            ('district_id', lambda col: col if aggregation_level > 1 else "'All'"),
            ('block_id', lambda col: col if aggregation_level > 2 else "'All'"),
            ('supervisor_id', lambda col: col if aggregation_level > 3 else "'All'"),
            ('awc_id', lambda col: col if aggregation_level > 4 else "'All'"),
            ('month', 'month'),
            ('ccs_status', 'ccs_status'),
            ('trimester', "'All'"),
            ('caste', "'All'"),
            ('disabled', "'All'"),
            ('minority', "'All'"),
            ('resident', "'All'"),
            ('valid_in_month', ),
            ('lactating', ),
            ('pregnant', ),
            ('thr_eligible', ),
            ('rations_21_plus_distributed', ),
            ('tetanus_complete', ),
            ('delivered_in_month', ),
            ('anc1_received_at_delivery', ),
            ('anc2_received_at_delivery', ),
            ('anc3_received_at_delivery', ),
            ('anc4_received_at_delivery', ),
            ('registration_trimester_at_delivery', 'AVG(registration_trimester_at_delivery)'),
            ('using_ifa', ),
            ('ifa_consumed_last_seven_days', ),
            ('anemic_normal', ),
            ('anemic_moderate', ),
            ('anemic_severe', ),
            ('anemic_unknown', ),
            ('extra_meal', ),
            ('resting_during_pregnancy', ),
            ('bp1_complete', ),
            ('bp2_complete', ),
            ('bp3_complete', ),
            ('pnc_complete', ),
            ('trimester_2', ),
            ('trimester_3', ),
            ('postnatal', ),
            ('counsel_bp_vid', ),
            ('counsel_preparation', ),
            ('counsel_immediate_bf', ),
            ('counsel_fp_vid', ),
            ('counsel_immediate_conception', ),
            ('counsel_accessible_postpartum_fp', ),
            ('has_aadhar_id', ),
            ('aggregation_level', str(aggregation_level)),
            ('valid_all_registered_in_month', ),
            ('institutional_delivery_in_month', ),
            ('lactating_all', ),
            ('pregnant_all', ),
            ('valid_visits', ),
            ('expected_visits', ),
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

        # in the future these may need to include more columns, but historically
        # caste, resident, minority and disabled have been skipped
        group_by = ["state_id", "month", "ccs_status"]
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

        return """
        INSERT INTO "{to_tablename}" (
            {columns}
        ) (
            SELECT {calculations}
            FROM "{from_tablename}"
            WHERE {child_is_test} = 0
            GROUP BY {group_by}
            ORDER BY {group_by}
        )
        """.format(
            to_tablename=self._tablename_func(aggregation_level),
            from_tablename=self._tablename_func(aggregation_level + 1),
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by),
            child_is_test=child_location
        )

    def indexes(self, aggregation_level):
        tablename = self._tablename_func(aggregation_level)
        indexes = [
            'CREATE INDEX ON "{}" (ccs_status)'.format(tablename),
        ]

        agg_locations = ['state_id']
        if aggregation_level > 1:
            indexes.append('CREATE INDEX ON "{}" (district_id)'.format(tablename))
            agg_locations.append('district_id')
        if aggregation_level > 2:
            indexes.append('CREATE INDEX ON "{}" (block_id)'.format(tablename))
            agg_locations.append('block_id')
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (supervisor_id)'.format(tablename))
            agg_locations.append('supervisor_id')

        indexes.append('CREATE INDEX ON "{}" ({})'.format(tablename, ', '.join(agg_locations)))
        return indexes
