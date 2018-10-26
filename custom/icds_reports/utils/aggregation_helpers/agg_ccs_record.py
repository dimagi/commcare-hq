from __future__ import absolute_import
from __future__ import unicode_literals

import six

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from six.moves import map

from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, transform_day_to_month


class AggCcsRecordAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'agg_ccs_record'

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    @property
    def ccs_record_monthly_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ccs_record_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id).decode('utf-8')

    def _tablename_func(self, agg_level):
        return "{}_{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"), agg_level)

    @property
    def tablename(self):
        return self._tablename_func(5)

    def drop_table_query(self):
        return 'DELETE FROM "{}"'.format(self.tablename)

    def aggregation_query(self):

        columns = (
            ('state_id', 'state_id'),
            ('district_id', 'district_id'),
            ('block_id', 'block_id'),
            ('supervisor_id', 'supervisor_id'),
            ('awc_id', 'ucr.awc_id'),
            ('month', 'ucr.month'),
            ('ccs_status', 'ucr.ccs_status'),
            ('trimester', "COALESCE(ucr.trimester::text, '') as coalesce_trimester"),
            ('caste', 'ucr.caste'),
            ('disabled', "COALESCE(ucr.disabled, 'no') as coalesce_disabled"),
            ('minority', "COALESCE(ucr.minority, 'no') as coalesce_minority"),
            ('resident', "COALESCE(ucr.resident,'no') as coalesce_resident"),
            ('valid_in_month', 'sum(ucr.valid_in_month)'),
            ('lactating', 'sum(ucr.lactating)'),
            ('pregnant', 'sum(ucr.pregnant)'),
            ('thr_eligible', 'sum(ucr.thr_eligible)'),
            ('rations_21_plus_distributed', 'sum(ucr.rations_21_plus_distributed)'),
            ('tetanus_complete', 'sum(ucr.tetanus_complete)'),
            ('delivered_in_month', 'sum(ucr.delivered_in_month)'),
            ('anc1_received_at_delivery', 'sum(ucr.anc1_received_at_delivery)'),
            ('anc2_received_at_delivery', 'sum(ucr.anc2_received_at_delivery)'),
            ('anc3_received_at_delivery', 'sum(ucr.anc3_received_at_delivery)'),
            ('anc4_received_at_delivery', 'sum(ucr.anc4_received_at_delivery)'),
            ('registration_trimester_at_delivery', 'avg(ucr.registration_trimester_at_delivery)'),
            ('using_ifa', 'sum(ucr.using_ifa)'),
            ('ifa_consumed_last_seven_days', 'sum(ucr.ifa_consumed_last_seven_days)'),
            ('anemic_normal', 'sum(ucr.anemic_normal)'),
            ('anemic_moderate', 'sum(ucr.anemic_moderate)'),
            ('anemic_severe', 'sum(ucr.anemic_severe)'),
            ('anemic_unknown', 'sum(ucr.anemic_unknown)'),
            ('extra_meal', 'sum(ucr.extra_meal)'),
            ('resting_during_pregnancy', 'sum(ucr.resting_during_pregnancy)'),
            ('bp1_complete', 'sum(ucr.bp1_complete)'),
            ('bp2_complete', 'sum(ucr.bp2_complete)'),
            ('bp3_complete', 'sum(ucr.bp3_complete)'),
            ('pnc_complete', 'sum(ucr.pnc_complete)'),
            ('trimester_2', 'sum(ucr.trimester_2)'),
            ('trimester_3', 'sum(ucr.trimester_3)'),
            ('postnatal', 'sum(ucr.postnatal)'),
            ('counsel_bp_vid', 'sum(ucr.counsel_bp_vid)'),
            ('counsel_preparation', 'sum(ucr.counsel_preparation)'),
            ('counsel_immediate_bf', 'sum(ucr.counsel_immediate_bf)'),
            ('counsel_fp_vid', 'sum(ucr.counsel_fp_vid)'),
            ('counsel_immediate_conception', 'sum(ucr.counsel_immediate_conception)'),
            ('counsel_accessible_postpartum_fp', 'sum(ucr.counsel_accessible_postpartum_fp)'),
            ('has_aadhar_id', 'sum(ucr.has_aadhar_id)'),
            ('aggregation_level', '5 '),
            ('valid_all_registered_in_month', 'sum(ucr.valid_all_registered_in_month)'),
            ('institutional_delivery_in_month', 'sum(ucr.institutional_delivery_in_month)'),
            ('lactating_all', 'sum(ucr.lactating_all)'),
            ('pregnant_all', 'sum(ucr.pregnant_all)'),
            ('valid_visits', 'sum(crm.valid_visits)'),
            ('expected_visits', 'floor(sum( '
             'CASE '
             'WHEN ucr.pregnant=1 THEN 0.44 '
             'WHEN ucr.month - ucr.add < 0 THEN 6 '
             'WHEN ucr.month - ucr.add < 182 THEN 1 '
             'ELSE 0.39 END'
             '))'),
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "{ucr_ccs_record_table}" ucr
            LEFT OUTER JOIN "{ccs_record_monthly_table}" as crm
            ON crm.case_id = ucr.doc_id and crm.month=ucr.month
            WHERE ucr.month = %(start_date)s AND state_id != ''
            GROUP BY state_id, district_id, block_id, supervisor_id, ucr.awc_id, ucr.month,
                     ucr.ccs_status, coalesce_trimester, ucr.caste, coalesce_disabled, coalesce_minority, coalesce_resident
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            ucr_ccs_record_table=self.ccs_record_monthly_ucr_tablename,
            ccs_record_monthly_table='ccs_record_monthly'
        ), {
            "start_date": self.month
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
        )

        def _transform_column(column_tuple):
            column = column_tuple[0]

            if len(column_tuple) == 2:
                agg_col = column_tuple[1]
                if isinstance(agg_col, six.string_types):
                    return column_tuple
                elif callable(agg_col):
                    return (column, agg_col(column))

            return (column, 'SUM({})'.format(column))

        columns = list(map(_transform_column, columns))

        # in the future these may need to include more columns, but historically
        # caste, resident, minority and disabled have been skipped
        group_by = ["state_id", "month", "ccs_status"]
        if aggregation_level > 1:
            group_by.append("district_id")
        if aggregation_level > 2:
            group_by.append("block_id")
        if aggregation_level > 3:
            group_by.append("supervisor_id")

        return """
        INSERT INTO "{to_tablename}" (
            {columns}
        ) (
            SELECT {calculations}
            FROM "{from_tablename}"
            GROUP BY {group_by}
            ORDER BY {group_by}
        )
        """.format(
            to_tablename=self._tablename_func(aggregation_level),
            from_tablename=self._tablename_func(aggregation_level + 1),
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by),
        )

    def indexes(self, aggregation_level):
        indexes = [
            'CREATE INDEX ON "{}" (ccs_status)'.format(self.tablename),
        ]

        agg_locations = ['state_id']
        if aggregation_level > 1:
            indexes.append('CREATE INDEX ON "{}" (district_id)'.format(self.tablename))
            agg_locations.append('district_id')
        if aggregation_level > 2:
            indexes.append('CREATE INDEX ON "{}" (block_id)'.format(self.tablename))
            agg_locations.append('block_id')
        if aggregation_level > 3:
            indexes.append('CREATE INDEX ON "{}" (supervisor_id)'.format(self.tablename))
            agg_locations.append('supervisor_id')

        indexes.append('CREATE INDEX ON "{}" ({})'.format(self.tablename, ', '.join(agg_locations)))
        return indexes
