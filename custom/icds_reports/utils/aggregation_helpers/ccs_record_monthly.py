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

    @property
    def person_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-person_cases_v2')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id).decode('utf-8')

    def aggregation_query(self):
        start_month_string = self.month.strftime("'%Y-%m-%d'::date")
        end_month_string = (self.month + relativedelta(months=1) - relativedelta(days=1)).strftime("'%Y-%m-%d'::date")
        age_in_days = "({} - case_list.dob)::integer".format(end_month_string)
        age_in_months_end = "({} / 30.4 )".format(age_in_days)
        age_in_months = "(({} - case_list.dob) / 30.4 )".format(start_month_string)
        open_in_month = ("(({} - case_list.opened_on::date)::integer >= 0)"
                         " AND (case_list.closed = 0"
                         " OR (case_list.closed_on::date - {})::integer > 0)").format(end_month_string,
                                                                                      start_month_string)
        alive_in_month = "(case_list.date_death IS NULL OR case_list.date_death - {} >= 0)".format(
            start_month_string)
        seeking_services = "(case_list.is_availing = 1 AND case_list.is_migrated = 0)"
        valid_in_month = "({} AND {} AND {} AND {} <= 72)".format(open_in_month, alive_in_month, seeking_services,
                                                                  age_in_months)
        add_in_month = "(case_list.add>= {} && case_list.add <= {})".format(start_month_string, end_month_string)
        delivered_in_month = "({} AND {} AND {})".format(seeking_services, add_in_month)
        thr_eligible = "({} AND {} > 6 AND {} <= 36)".format(valid_in_month, age_in_months_end, age_in_months)
        extra_meal = "(case_list.eating_extra_meal_last_visit AND case_list.pregnant)"
        b1_complete = "(case_list.bp1_date <= {})".format(end_month_string)
        b2_complete = "(case_list.bp2_date <= {})".format(end_month_string)
        b3_complete = "(case_list.bp3_date <= {})".format(end_month_string)
        pregnant_to_count = "(case_list.pregnant AND {} AND not case_list.is_migrated)".format(seeking_services)
        pregnant_all = "(case_list.pregnant AND not case_list.is_migrated)"
        trimester = "CASE WHEN case_list.pregnant THEN  CASE WHEN case_list.edd-end_month_string>=183" \
                    "THEN 1 ELSE CASE WHEN case_list.edd-end_month_string<91 THEN 3 ELSE 2 End END ELSE null"
        ccs_lactating = "({} AND {} AND case_list.add not in ('',null) AND {}-case_list.add>=0" \
                        " AND {}-case_list.add<=183)".format(open_in_month, alive_in_month,
                                                            end_month_string, start_month_string)
        lactating = "({} AND {} AND not case_list.is_migrated)".format(ccs_lactating, seeking_services)
        lactating_all = "({} AND not case_list.is_migrated)".format(ccs_lactating)
        postnatal = "(case_list.add not in ('',null) AND {}-case_list.add>=0 AND {}-case_list.add<21" \
                    " AND {} AND not case_list.is_migrated AND {} AND {})".format(end_month_string, start_month_string,
                                                                                  seeking_services, alive_in_month,
                                                                                  open_in_month)
        columns = (
            ('awc_id', 'case_list.awc_id'),
            ('case_id', 'case_list.case_id'),
            ('month', self.month.strftime("'%Y-%m-%d'")),
            ('age_in_months', 'trunc({})'.format(age_in_months_end)),
            ('ccs_status', "CASE WHEN {} THEN 'pregnant' ELSE CASE WHEN {} THEN "
                           "'lactating' ELSE 'other' END END".format(pregnant_to_count,
                                                                     lactating)),
            ('open_in_month', "CASE WHEN {} THEN 1 ELSE 0 END".format(open_in_month)),
            ('alive_in_month', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(alive_in_month)),
            ('trimester', trimester),
            ('num_rations_distributed', 'COALESCE(agg_thr.days_ration_given_mother, 0)'),
            ('thr_eligible', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(thr_eligible)),
            ('tetanus_complete', 'ucr.tetanus_complete'),
            ('delivered_in_month', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(delivered_in_month)),
            ('anc1_received_at_delivery', 'CASE WHEN {} AND case_list.anc1_received THEN 1 ELSE 0'.format(delivered_in_month)),
            ('anc2_received_at_delivery', 'CASE WHEN {} AND case_list.anc2_received THEN 1 ELSE 0'.format(delivered_in_month)),
            ('anc3_received_at_delivery', 'CASE WHEN {} AND case_list.anc3_received THEN 1 ELSE 0'.format(delivered_in_month)),
            ('anc4_received_at_delivery', 'CASE WHEN {} AND case_list.anc4_received THEN 1 ELSE 0'.format(delivered_in_month)),
            ('registration_trimester_at_delivery', 'CASE WHEN {} THEN {} ELSE null'.format(delivered_in_month, trimester)),
            ('using_ifa', 'case_list.using_ifa_last_visit'),
            ('ifa_consumed_last_seven_days', 'ucr.ifa_consumed_last_seven_days'),
            ('anemic_severe', "CASE WHEN case_list.anemia_status_last_visit='severe' THEN 1 WHERE 0"),
            ('anemic_moderate', "CASE WHEN case_list.anemia_status_last_visit='moderate' THEN 1 WHERE 0"),
            ('anemic_normal', "CASE WHEN case_list.anemia_status_last_visit='normal' THEN 1 WHERE 0"),
            ('anemic_unknown', "CASE WHEN case_list.anemia_status_last_visit not in ('normal','severe','moderate') THEN 1 WHERE 0"),
            ('extra_meal', 'CASE WHEN {} THEN 1 ELSE 0'.format(extra_meal)),
            ('resting_during_pregnancy', 'ucr.resting_during_pregnancy'),
            ('bp_visited_in_month', 'ucr.bp_visited_in_month'),
            ('pnc_visited_in_month', 'NULL'),
            ('trimester_2', 'CASE WHEN {}=2 THEN 1 ELSE 0'.format(trimester)),
            ('trimester_3', 'CASE WHEN {}=3 THEN 1 ELSE 0'.format(trimester)),
            ('counsel_immediate_bf', 'ucr.counsel_immediate_bf'),
            ('counsel_bp_vid', 'ucr.counsel_bp_vid'),
            ('counsel_preparation', 'ucr.counsel_preparation'),
            ('counsel_fp_vid', 'ucr.counsel_fp_vid'),
            ('counsel_immediate_conception', 'ucr.counsel_immediate_conception'),
            ('counsel_accessible_postpartum_fp', 'ucr.counsel_accessible_postpartum_fp'),
            ('bp1_complete', 'CASE WHEN {} THEN 1 ELSE 0'.format(b1_complete)),
            ('bp2_complete', 'CASE WHEN {} THEN 1 ELSE 0'.format(b2_complete)),
            ('bp3_complete', 'CASE WHEN {} THEN 1 ELSE 0'.format(b3_complete)),
            ('pnc_complete', 'ucr.pnc_complete'),
            ('postnatal', 'CASE WHEN {} THEN 1 ELSE 0'.format(postnatal)),
            ('has_aadhar_id', "CASE WHEN person_cases.aadhar_date < {} THEN  1 ELSE 0 END".format(end_month_string)),
            ('counsel_fp_methods', 'NULL'),
            ('pregnant', 'CASE WHEN {} THEN 1 ELSE 0'.format(pregnant_to_count)),
            ('pregnant_all', 'CASE WHEN {} THEN 1 ELSE 0'.format(pregnant_all)),
            ('lactating', 'CASE WHEN {} THEN 1 ELSE 0'.format(lactating)),
            ('lactating_all', 'CASE WHEN {} THEN 1 ELSE 0'.format(lactating_all)),
            ('institutional_delivery_in_month', 'ucr.institutional_delivery_in_month'),
            ('add', 'case_list.add'),
            ('caste', 'case_list.caste'),
            ('disabled', 'case_list.disabled'),
            ('minority', 'case_list.minority'),
            ('resident', 'case_list.resident'),
            ('valid_in_month', "CASE WHEN {} THEN 1 ELSE 0 END".format(valid_in_month)),
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
            ('valid_visits', '('
                'COALESCE(agg_cf.valid_visits, 0) + '
                'COALESCE(agg_bp.valid_visits, 0) + '
                'COALESCE(agg_pnc.valid_visits, 0) + '
                'COALESCE(agg_delivery.valid_visits, 0)'
             ')'),
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
            LEFT OUTER JOIN "{person_cases_ucr}" person_cases ON child_health.mother_id = person_cases.doc_id
                AND child_health.state_id = person_cases.state_id
                AND lower(substring(person_cases.state_id, '.{{3}}$'::text)) = %(state_id_last_3)s
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
            person_cases_ucr=self.person_case_ucr_tablename,
        ), {
            "start_date": self.month,
            "end_date": self.end_date
        }

    def indexes(self):
        return [
            'CREATE INDEX ON "{}" (awc_id, case_id)'.format(self.tablename),
        ]
