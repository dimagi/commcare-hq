from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import (
    AGG_CCS_RECORD_BP_TABLE,
    AGG_CCS_RECORD_PNC_TABLE,
    AGG_CCS_RECORD_THR_TABLE,
    AGG_CCS_RECORD_DELIVERY_TABLE,
    AGG_CCS_RECORD_CF_TABLE)
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, transform_day_to_month


class CcsRecordMonthlyAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'ccs_record_monthly'

    def __init__(self, month):
        self.month = transform_day_to_month(month)
        self.end_date = transform_day_to_month(month + relativedelta(months=1, seconds=-1))

    @property
    def ccs_record_monthly_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ccs_record_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id).decode('utf-8')

    @property
    def ccs_record_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-ccs_record_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id).decode('utf-8')

    @property
    def pregnant_tasks_cases_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-pregnant-tasks_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id).decode('utf-8')

    @property
    def tablename(self):
        return "{}_{}".format(self.base_tablename, self.month.strftime("%Y-%m-%d"))

    def drop_table_query(self):
        return 'DELETE FROM "{}"'.format(self.tablename)

    def aggregation_query(self):

        columns = (
            ('awc_id', 'ucr.awc_id'),
            ('case_id', 'ucr.case_id'),
            ('month', 'ucr.month'),
            ('age_in_months', 'ucr.age_in_months'),
            ('ccs_status', 'ucr.ccs_status'),
            ('open_in_month', 'ucr.open_in_month'),
            ('alive_in_month', 'ucr.alive_in_month'),
            ('trimester', 'ucr.trimester'),
            ('num_rations_distributed', 'COALESCE(agg_thr.days_ration_given_mother, 0)'),
            ('thr_eligible', 'ucr.thr_eligible'),
            ('tetanus_complete', 'ucr.tetanus_complete'),
            ('delivered_in_month', 'ucr.delivered_in_month'),
            ('anc1_received_at_delivery', 'ucr.anc1_received_at_delivery'),
            ('anc2_received_at_delivery', 'ucr.anc2_received_at_delivery'),
            ('anc3_received_at_delivery', 'ucr.anc3_received_at_delivery'),
            ('anc4_received_at_delivery', 'ucr.anc4_received_at_delivery'),
            ('registration_trimester_at_delivery', 'ucr.registration_trimester_at_delivery'),
            ('using_ifa', 'ucr.using_ifa'),
            ('ifa_consumed_last_seven_days', 'ucr.ifa_consumed_last_seven_days'),
            ('anemic_severe', 'ucr.anemic_severe'),
            ('anemic_moderate', 'ucr.anemic_moderate'),
            ('anemic_normal', 'ucr.anemic_normal'),
            ('anemic_unknown', 'ucr.anemic_unknown'),
            ('extra_meal', 'ucr.extra_meal'),
            ('resting_during_pregnancy', 'ucr.resting_during_pregnancy'),
            ('bp_visited_in_month', 'ucr.bp_visited_in_month'),
            ('pnc_visited_in_month', 'NULL'),
            ('trimester_2', 'ucr.trimester_2'),
            ('trimester_3', 'ucr.trimester_3'),
            ('counsel_immediate_bf', 'ucr.counsel_immediate_bf'),
            ('counsel_bp_vid', 'ucr.counsel_bp_vid'),
            ('counsel_preparation', 'ucr.counsel_preparation'),
            ('counsel_fp_vid', 'ucr.counsel_fp_vid'),
            ('counsel_immediate_conception', 'ucr.counsel_immediate_conception'),
            ('counsel_accessible_postpartum_fp', 'ucr.counsel_accessible_postpartum_fp'),
            ('bp1_complete', 'ucr.bp1_complete'),
            ('bp2_complete', 'ucr.bp2_complete'),
            ('bp3_complete', 'ucr.bp3_complete'),
            ('pnc_complete', 'ucr.pnc_complete'),
            ('postnatal', 'ucr.postnatal'),
            ('has_aadhar_id', 'ucr.has_aadhar_id'),
            ('counsel_fp_methods', 'NULL'),
            ('pregnant', 'ucr.pregnant'),
            ('pregnant_all', 'ucr.pregnant_all'),
            ('lactating', 'ucr.lactating'),
            ('lactating_all', 'ucr.lactating_all'),
            ('institutional_delivery_in_month', 'ucr.institutional_delivery_in_month'),
            ('add', 'ucr.add'),
            ('caste', 'ucr.caste'),
            ('disabled', 'ucr.disabled'),
            ('minority', 'ucr.minority'),
            ('resident', 'ucr.resident'),
            ('valid_in_month', 'ucr.valid_in_month'),
            ('anc_in_month',
             '( '
                '(CASE WHEN ut.due_list_date_anc_1 BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) + '
                '(CASE WHEN ut.due_list_date_anc_2 BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) + '
                '(CASE WHEN ut.due_list_date_anc_3 BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) + '
                '(CASE WHEN ut.due_list_date_anc_4 BETWEEN %(start_date)s AND %(end_date)s THEN 1 ELSE 0 END) '
                ')'),
            ('anc_1', 'ut.due_list_date_anc_1'),
            ('anc_2', 'ut.due_list_date_anc_2'),
            ('anc_3', 'ut.due_list_date_anc_3'),
            ('anc_4', 'ut.due_list_date_anc_4'),
            ('tt_1', 'ut.due_list_date_tt_1'),
            ('tt_2', 'ut.due_list_date_tt_2'),
            ('immediate_breastfeeding', 'agg_bp.immediate_breastfeeding'),
            ('anemia', 'agg_bp.anemia'),
            ('eating_extra', 'agg_bp.eating_extra'),
            ('resting', 'agg_bp.resting'),
            ('anc_weight', 'agg_bp.anc_weight'),
            ('anc_blood_pressure', 'agg_bp.anc_blood_pressure'),
            ('bp_sys', 'agg_bp.bp_sys'),
            ('bp_dia', 'agg_bp.bp_dia'),
            ('anc_hemoglobin', 'agg_bp.anc_hemoglobin'),
            ('bleeding', 'agg_bp.bleeding'),
            ('swelling', 'agg_bp.swelling'),
            ('blurred_vision', 'agg_bp.blurred_vision'),
            ('convulsions', 'agg_bp.convulsions'),
            ('rupture', 'agg_bp.rupture'),
            ('bp_date', 'agg_bp.latest_time_end_processed::DATE'),
            ('is_ebf', 'agg_pnc.is_ebf'),
            ('breastfed_at_birth', 'agg_delivery.breastfed_at_birth'),
            ('person_name', 'case_list.person_name'),
            ('edd', 'case_list.edd'),
            ('delivery_nature', 'case_list.delivery_nature'),
            ('mobile_number', 'case_list.mobile_number'),
            ('preg_order', 'case_list.preg_order'),
            ('num_pnc_visits', 'case_list.num_pnc_visits'),
            ('last_date_thr', 'case_list.last_date_thr'),
            ('num_anc_complete', 'case_list.num_anc_complete'),
            ('valid_visits', 'agg_cf.valid_visits + agg_bp.valid_visits + agg_pnc.valid_visits'),
            ('opened_on', 'case_list.opened_on'),
            ('dob', 'case_list.dob')
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "{ucr_ccs_record_monthly_table}" ucr
            LEFT OUTER JOIN "{agg_thr_table}" agg_thr ON ucr.doc_id = agg_thr.case_id AND ucr.month = agg_thr.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{agg_bp_table}" agg_bp ON ucr.doc_id = agg_bp.case_id AND ucr.month = agg_bp.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{agg_pnc_table}" agg_pnc ON ucr.doc_id = agg_pnc.case_id AND ucr.month = agg_pnc.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{agg_cf_table}" agg_cf ON ucr.doc_id = agg_cf.case_id AND ucr.month = agg_cf.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{agg_delivery_table}" agg_delivery ON ucr.doc_id = agg_delivery.case_id AND ucr.month = agg_delivery.month and ucr.valid_in_month = 1
            LEFT OUTER JOIN "{ccs_record_case_ucr}" case_list ON ucr.doc_id = case_list.doc_id
            LEFT OUTER JOIN "{pregnant_tasks_case_ucr}" ut ON ucr.doc_id = ut.ccs_record_case_id
            WHERE ucr.month = %(start_date)s
            ORDER BY ucr.awc_id, ucr.case_id
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            ucr_ccs_record_monthly_table=self.ccs_record_monthly_ucr_tablename,
            agg_thr_table=AGG_CCS_RECORD_THR_TABLE,
            ccs_record_case_ucr=self.ccs_record_case_ucr_tablename,
            agg_pnc_table=AGG_CCS_RECORD_PNC_TABLE,
            agg_bp_table=AGG_CCS_RECORD_BP_TABLE,
            agg_delivery_table=AGG_CCS_RECORD_DELIVERY_TABLE,
            pregnant_tasks_case_ucr=self.pregnant_tasks_cases_ucr_tablename,
            agg_cf_table=AGG_CCS_RECORD_CF_TABLE,
        ), {
            "start_date": self.month,
            "end_date": self.end_date
        }

    def indexes(self):
        return [
            'CREATE INDEX ON "{}" (awc_id, case_id)'.format(self.tablename),
        ]
