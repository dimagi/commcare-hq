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
from custom.icds_reports.utils.aggregation_helpers import transform_day_to_month, month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper


class CcsRecordMonthlyAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'ccs-record-monthly'
    tablename = 'ccs_record_monthly'

    def __init__(self, month):
        self.month = transform_day_to_month(month)
        self.end_date = transform_day_to_month(month + relativedelta(months=1, seconds=-1))

    def aggregate(self, cursor):
        drop_query, drop_params = self.drop_table_query()
        agg_query, agg_params = self.aggregation_query()
        index_queries = self.indexes()

        cursor.execute(drop_query, drop_params)
        cursor.execute(agg_query, agg_params)
        for query in index_queries:
            cursor.execute(query)

    @property
    def ccs_record_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-ccs_record_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def pregnant_tasks_cases_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-pregnant-tasks_cases')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def person_case_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, 'static-person_cases_v3')
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def drop_table_query(self):
        return (
            'DELETE FROM "{}" WHERE month=%(month)s'.format(self.tablename),
            {'month': month_formatter(self.month)}
        )

    def aggregation_query(self):
        start_month_string = self.month.strftime("'%Y-%m-%d'::date")
        end_month_string = (self.month + relativedelta(months=1, days=-1)).strftime("'%Y-%m-%d'::date")
        age_in_days = "({} - person_cases.dob)::integer".format(end_month_string)
        age_in_months_end = "({} / 30.4 )".format(age_in_days)
        open_in_month = (
            "({} - case_list.opened_on::date)::integer >= 0"
            " AND (case_list.closed = 0"
            " OR (case_list.closed_on::date - {})::integer > 0)"
        ).format(end_month_string, start_month_string)

        alive_in_month = "(case_list.date_death is null OR case_list.date_death-{}>0)".format(start_month_string)
        seeking_services = "(case_list.is_availing = 1 AND case_list.is_migrated = 0)"
        ccs_lactating = (
            "({} AND {} AND case_list.add is not null AND {}-case_list.add>=0"
            " AND {}-case_list.add<=183)"
        ).format(open_in_month, alive_in_month, end_month_string, start_month_string)

        lactating = "({} AND {})".format(ccs_lactating, seeking_services)
        lactating_all = "({} AND  case_list.is_migrated=0)".format(ccs_lactating)

        ccs_pregnant = (
            "({} AND {} AND case_list.edd is not null and"
            " (case_list.add is null OR case_list.add>{}))"
        ).format(open_in_month, alive_in_month, end_month_string)

        pregnant_to_consider = "({} AND {} AND {} AND {})".format(
            ccs_pregnant, seeking_services, open_in_month, alive_in_month
        )

        pregnant_all = "({} AND  case_list.is_migrated=0)".format(ccs_pregnant)

        valid_in_month = "( {} OR {})".format(pregnant_to_consider, lactating)

        add_in_month = "(case_list.add>= {} AND case_list.add<={})".format(start_month_string, end_month_string)
        add_in_month_after_opened_on = "({} AND case_list.opened_on<=case_list.add)".format(add_in_month)
        delivered_in_month = "({} AND {})".format(seeking_services, add_in_month_after_opened_on)
        extra_meal = "(agg_bp.eating_extra=1 AND {})".format(pregnant_to_consider)
        b1_complete = "(case_list.bp1_date <= {})".format(end_month_string)
        b2_complete = "(case_list.bp2_date <= {})".format(end_month_string)
        b3_complete = "(case_list.bp3_date <= {})".format(end_month_string)

        trimester = (
            "(CASE WHEN {} THEN  CASE WHEN (case_list.edd-{})::integer>=183"
            "THEN 1 ELSE CASE WHEN (case_list.edd-{})::integer<91"
            "THEN 3 ELSE 2 END END ELSE null END)"
        ).format(pregnant_to_consider, end_month_string, end_month_string)

        registration_trimester = (
            "(CASE WHEN (case_list.edd-case_list.opened_on::date)::integer>=183"
            "THEN 1 ELSE CASE WHEN (case_list.edd-case_list.opened_on::date)::integer<91"
            "THEN 3 ELSE 2 END END)"
        )

        postnatal = (
            "(case_list.add is not null AND ({}-case_list.add)::integer>=0 AND "
            "({}-case_list.add)::integer<=21)"
        ).format(end_month_string, start_month_string)

        tetanus_complete = (
            "({} AND ut.tt_complete_date is not null AND "
            "ut.tt_complete_date<={})"
        ).format(pregnant_to_consider, end_month_string)

        pnc_complete = "(case_list.pnc1_date is not null AND case_list.pnc1_date<{})".format(end_month_string)
        bp_visited_in_month = "date_trunc('MONTH', agg_bp.latest_time_end_processed)={}".format(start_month_string)

        columns = (
            ('awc_id', 'case_list.awc_id'),
            ('case_id', 'case_list.case_id'),
            ('supervisor_id', 'case_list.supervisor_id'),
            ('month', self.month.strftime("'%Y-%m-%d'")),
            ('age_in_months', 'trunc({})'.format(age_in_months_end)),
            ('ccs_status', "CASE WHEN {} THEN 'pregnant' ELSE CASE WHEN {} THEN "
                           "'lactating' ELSE 'other' END END".format(pregnant_to_consider,
                                                                     lactating)),
            ('open_in_month', "CASE WHEN {} THEN 1 ELSE 0 END".format(open_in_month)),
            ('alive_in_month', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(alive_in_month)),
            ('trimester', trimester),
            ('num_rations_distributed', 'COALESCE(agg_thr.days_ration_given_mother, 0)'),
            ('thr_eligible', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(valid_in_month)),
            ('tetanus_complete', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(tetanus_complete)),
            ('delivered_in_month', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(delivered_in_month)),
            ('anc1_received_at_delivery', 'CASE WHEN {} AND case_list.anc1_received=1 '
                                          'THEN 1 ELSE 0 END'.format(delivered_in_month)),
            ('anc2_received_at_delivery', 'CASE WHEN {} AND case_list.anc2_received=1 '
                                          'THEN 1 ELSE 0 END'.format(delivered_in_month)),
            ('anc3_received_at_delivery', 'CASE WHEN {} AND case_list.anc3_received=1 '
                                          'THEN 1 ELSE 0 END'.format(delivered_in_month)),
            ('anc4_received_at_delivery', 'CASE WHEN {} AND case_list.anc4_received=1 '
                                          'THEN 1 ELSE 0 END'.format(delivered_in_month)),
            ('registration_trimester_at_delivery', 'CASE WHEN {} '
                                                   'THEN {} ELSE null END'.format(delivered_in_month,
                                                                                  registration_trimester)),
            ('using_ifa', 'CASE WHEN {} and agg_bp.using_ifa=1 THEN 1 ELSE 0 END'.format(pregnant_to_consider)),
            ('ifa_consumed_last_seven_days', 'CASE WHEN {}>1 AND agg_bp.ifa_last_seven_days>=4 THEN'
                                             ' 1 ELSE 0 END'.format(trimester)),
            ('anemic_severe', "CASE WHEN agg_bp.anemia=1 THEN 1 ELSE 0 END"),
            ('anemic_moderate', "CASE WHEN agg_bp.anemia=2 THEN 1 ELSE 0 END"),
            ('anemic_normal', "CASE WHEN agg_bp.anemia=3 THEN 1 ELSE 0 END"),
            ('anemic_unknown', "CASE WHEN agg_bp.anemia is NULL THEN 1 "
                               "ELSE CASE WHEN agg_bp.anemia not in (1,2,3)"
                               "THEN 1 ELSE 0 END END"),
            ('extra_meal', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(extra_meal)),
            ('resting_during_pregnancy', 'CASE WHEN {} THEN COALESCE(agg_bp.resting, 0)'
                                         'ELSE 0 END '.format(pregnant_to_consider)),
            ('bp_visited_in_month', 'CASE WHEN {}  THEN 1 ELSE 0 END'.format(bp_visited_in_month)),
            ('pnc_visited_in_month', 'NULL'),
            ('trimester_2', 'CASE WHEN {}=2 THEN 1 ELSE 0 END'.format(trimester)),
            ('trimester_3', 'CASE WHEN {}=3 THEN 1 ELSE 0 END'.format(trimester)),
            ('counsel_immediate_bf', 'CASE WHEN {}=3 THEN COALESCE(agg_bp.immediate_breastfeeding,0) '
                                     'ELSE 0 END'.format(trimester)),
            ('counsel_bp_vid', 'CASE WHEN {}=3 THEN COALESCE(agg_bp.play_birth_preparedness_vid,0) '
                               'ELSE 0 END'.format(trimester)),
            ('counsel_preparation', 'CASE WHEN {}=3 THEN COALESCE(agg_bp.counsel_preparation,0) '
                                    'ELSE 0 END'.format(trimester)),
            ('counsel_fp_vid', 'CASE WHEN {}=3 THEN COALESCE(agg_bp.play_family_planning_vid,0) '
                               'ELSE 0 END'.format(trimester)),
            ('counsel_immediate_conception', 'CASE WHEN {}=3 THEN COALESCE(agg_bp.conceive,0) '
                                             'ELSE 0 END'.format(trimester)),
            ('counsel_accessible_postpartum_fp', 'CASE WHEN {}=3 THEN COALESCE(agg_bp.counsel_accessible_ppfp,0) '
                                                 'ELSE 0 END'.format(trimester)),
            ('bp1_complete', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(b1_complete)),
            ('bp2_complete', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(b2_complete)),
            ('bp3_complete', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(b3_complete)),
            ('pnc_complete', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(pnc_complete)),
            ('postnatal', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(postnatal)),
            ('has_aadhar_id', "CASE WHEN person_cases.aadhar_date < {} THEN"
                              "  1 ELSE 0 END".format(end_month_string)),
            ('counsel_fp_methods', 'NULL'),
            ('pregnant', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(pregnant_to_consider)),
            ('pregnant_all', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(pregnant_all)),
            ('lactating', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(lactating)),
            ('lactating_all', 'CASE WHEN {} THEN 1 ELSE 0 END'.format(lactating_all)),
            ('institutional_delivery_in_month', 'CASE WHEN agg_delivery.where_born=2 AND {} THEN'
                                                ' 1 ELSE 0 END'.format(delivered_in_month)),
            ('add', 'case_list.add'),
            ('caste', 'case_list.caste'),
            ('disabled', 'case_list.disabled'),
            ('minority', 'case_list.minority'),
            ('resident', 'case_list.resident'),
            ('valid_in_month', "CASE WHEN {} THEN 1 ELSE 0 END".format(valid_in_month)),
            ('institutional_delivery', 'case_list.institutional_delivery'),
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
            ('person_name', 'person_cases.name'),
            ('edd', 'case_list.edd'),
            ('delivery_nature', 'case_list.delivery_nature'),
            ('mobile_number', 'person_cases.phone_number'),
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
            ('dob', 'person_cases.dob'),
            ('closed', 'case_list.closed'),
            ('anc_abnormalities', 'agg_bp.anc_abnormalities'),
            ('home_visit_date', 'agg_bp.latest_time_end_processed'),
            ('date_death', 'person_cases.date_death'),
            ('person_case_id', 'case_list.person_case_id'),
            ('child_name', 'case_list.child_name')
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "{ccs_record_case_ucr}" case_list
            LEFT OUTER JOIN "{person_cases_ucr}" person_cases ON case_list.person_case_id = person_cases.doc_id
                AND case_list.supervisor_id = person_cases.supervisor_id
            LEFT OUTER JOIN "{pregnant_tasks_case_ucr}" ut ON case_list.doc_id = ut.ccs_record_case_id
                AND case_list.supervisor_id = ut.supervisor_id
            LEFT OUTER JOIN "{agg_thr_table}" agg_thr ON case_list.doc_id = agg_thr.case_id
                AND agg_thr.month = %(start_date)s AND {valid_in_month}
                AND case_list.supervisor_id = agg_thr.supervisor_id
            LEFT OUTER JOIN "{agg_bp_table}" agg_bp ON case_list.doc_id = agg_bp.case_id
                AND agg_bp.month = %(start_date)s AND {valid_in_month}
                AND case_list.supervisor_id = agg_bp.supervisor_id
            LEFT OUTER JOIN "{agg_pnc_table}" agg_pnc ON case_list.doc_id = agg_pnc.case_id
                AND agg_pnc.month = %(start_date)s AND {valid_in_month}
                AND case_list.supervisor_id = agg_pnc.supervisor_id
            LEFT OUTER JOIN "{agg_cf_table}" agg_cf ON case_list.doc_id = agg_cf.case_id
                AND agg_cf.month = %(start_date)s AND {valid_in_month}
                AND case_list.supervisor_id = agg_cf.supervisor_id
            LEFT OUTER JOIN "{agg_delivery_table}" agg_delivery ON case_list.doc_id = agg_delivery.case_id
                AND agg_delivery.month = %(start_date)s AND {valid_in_month}
                AND case_list.supervisor_id = agg_delivery.supervisor_id
            WHERE {open_in_month} AND (case_list.add is NULL OR %(start_date)s-case_list.add<=183)
                AND case_list.supervisor_id IS NOT NULL
            ORDER BY case_list.supervisor_id, case_list.awc_id, case_list.case_id, case_list.modified_on
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            agg_thr_table=AGG_CCS_RECORD_THR_TABLE,
            ccs_record_case_ucr=self.ccs_record_case_ucr_tablename,
            agg_pnc_table=AGG_CCS_RECORD_PNC_TABLE,
            agg_bp_table=AGG_CCS_RECORD_BP_TABLE,
            agg_delivery_table=AGG_CCS_RECORD_DELIVERY_TABLE,
            pregnant_tasks_case_ucr=self.pregnant_tasks_cases_ucr_tablename,
            agg_cf_table=AGG_CCS_RECORD_CF_TABLE,
            person_cases_ucr=self.person_case_ucr_tablename,
            valid_in_month=valid_in_month,
            open_in_month=open_in_month
        ), {
            "start_date": self.month,
            "end_date": self.end_date,

        }

    def indexes(self):
        return [
            'CREATE INDEX IF NOT EXISTS crm_awc_case_idx ON "{}" (awc_id, case_id)'.format(self.tablename),
            'CREATE INDEX IF NOT EXISTS crm_person_add_case_idx ON "{}" (person_case_id, add, case_id)'.format(
                self.tablename
            )
        ]
