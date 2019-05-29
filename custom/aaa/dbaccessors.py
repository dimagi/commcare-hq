from __future__ import absolute_import, unicode_literals
from __future__ import division

from collections import OrderedDict
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db import connections
from django.db.models import (
    Case,
    IntegerField,
    Sum,
    When,
    F,
    Value,
    ExpressionWrapper,
)

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import get_aaa_db_alias
from custom.aaa.models import (
    CcsRecord,
    Child,
    ChildHistory,
    Woman,
)
from dimagi.utils.dates import force_to_datetime
from six.moves import zip


class ChildQueryHelper(object):
    def __init__(self, domain, person_case_id, date_):
        self.domain = domain
        self.person_case_id = person_case_id
        self.date_ = date_

    @classmethod
    def list(cls, domain, date_, location_filters, sort_column):
        return Child.objects.filter(
            domain=domain,
            dob__range=(date_ - relativedelta(years=5), date_),
            **location_filters
        ).annotate(
            age_in_months=ExpressionWrapper(
                (Value(date_) - F('dob')) / Value(30.417),
                output_field=IntegerField()
            )
        ).extra(
            select={
                'lastImmunizationType': 'last_immunization_type',
                'lastImmunizationDate': 'last_immunization_date',
                'gender': 'sex',
                'id': 'person_case_id',
            }
        ).values(
            'id', 'name', 'dob', 'gender', 'lastImmunizationType', 'lastImmunizationDate', 'age_in_months'
        ).order_by(sort_column)

    def infant_details(self):
        extra_select = {
            'breastfeedingInitiated': 'breastfed_within_first',
            'dietDiversity': 'diet_diversity',
            'birthWeight': 'birth_weight',
            'dietQuantity': 'diet_quantity',
            'breastFeeding': 'comp_feeding',
            'handwash': 'hand_wash',
            'exclusivelyBreastfed': 'is_exclusive_breastfeeding',
            'babyCried': 'child_cried',
            'pregnancyLength': "'N/A'",
        }

        return Child.objects.extra(
            select=extra_select
        ).values(*list(extra_select.keys())).get(
            domain=self.domain,
            person_case_id=self.person_case_id,
        )

    def postnatal_care_details(self):
        ret = []
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        pnc_details = child.postnatal_care_form_details(self.date_)
        for detail in pnc_details:
            ret.append({
                'pncDate': detail['timeend'].date(),
                'breastfeeding': detail['breastfeeding_well'] or 'N/A',
                'skinToSkinContact': detail['skin_to_skin'] or 'N/A',
                'wrappedUpAdequately': detail['wrapped'] or 'N/A',
                'awakeActive': detail['baby_active'] or 'N/A',
            })
        return ret

    def vaccination_details(self, period):
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        task_case = child.task_case_details()

        def _safe_date_get(name):
            ret = task_case.get('due_list_date_{}'.format(name), 'N/A')
            if ret == date(1970, 1, 1):
                # This is the default date in the UCR framework, but will never happen in the project
                return 'N/A'
            return ret

        if period == 'atBirth':
            return [
                {'vitaminName': 'BCG', 'date': _safe_date_get('1g_bcg'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Hepatitis B - 1', 'date': _safe_date_get('1g_hep_b_1'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'OPV - 0', 'date': _safe_date_get('0g_opv_0'), 'adverseEffects': 'N/A'},
            ]
        elif period == 'sixWeek':
            return [
                {'vitaminName': 'OPV - 1', 'date': _safe_date_get('1g_opv_1'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 1', 'date': _safe_date_get('1g_penta_1'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Fractional IPV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},  # not tracked
                {'vitaminName': 'Rotavirus - 1', 'date': _safe_date_get('1g_rv_1'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'PCV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},  # not tracked
            ]
        elif period == 'tenWeek':
            return [
                {'vitaminName': 'OPV - 2', 'date': _safe_date_get('2g_opv_2'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 2', 'date': _safe_date_get('2g_penta_2'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 2', 'date': _safe_date_get('2g_rv_2'), 'adverseEffects': 'N/A'},
            ]
        elif period == 'fourteenWeek':
            return [
                {'vitaminName': 'OPV - 3', 'date': _safe_date_get('3g_opv_3'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 3', 'date': _safe_date_get('3g_penta_3'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Fractional IPV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},  # not tracked
                {'vitaminName': 'Rotavirus - 3', 'date': _safe_date_get('3g_rv_3'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'PCV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},  # not tracked
            ]
        elif period == 'nineTwelveMonths':
            return [
                {'vitaminName': 'PCV Booster', 'date': 'N/A', 'adverseEffects': 'N/A'},  # not tracked
                {'vitaminName': 'Vit. A - 1', 'date': _safe_date_get('4g_vit_a_1'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Measles - 1', 'date': _safe_date_get('4g_measles'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'JE - 1', 'date': _safe_date_get('4g_je_1'), 'adverseEffects': 'N/A'},
            ]
        elif period == 'sixTeenTwentyFourMonth':
            return [
                {'vitaminName': 'DPT Booster - 1', 'date': _safe_date_get('1g_dpt_1'), 'adverseEffects': 'N/A'},
                {
                    'vitaminName': 'Measles - 2',
                    'date': _safe_date_get('5g_measles_booster'),
                    'adverseEffects': 'N/A'
                },
                {'vitaminName': 'OPV Booster', 'date': _safe_date_get('5g_opv_booster'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'JE - 2', 'date': _safe_date_get('5g_je_2'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 2', 'date': _safe_date_get('5g_vit_a_2'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 3', 'date': _safe_date_get('6g_vit_a_3'), 'adverseEffects': 'N/A'},
            ]
        elif period == 'twentyTwoSeventyTwoMonth':
            return [
                {'vitaminName': 'Vit. A - 4', 'date': _safe_date_get('6g_vit_a_4'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 5', 'date': _safe_date_get('6g_vit_a_5'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 6', 'date': _safe_date_get('6g_vit_a_6'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 7', 'date': _safe_date_get('6g_vit_a_7'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 8', 'date': _safe_date_get('6g_vit_a_8'), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 9', 'date': _safe_date_get('6g_vit_a_9'), 'adverseEffects': 'N/A'},
                {
                    'vitaminName': 'DPT Booster - 2',
                    'date': _safe_date_get('7gdpt_booster_2'),
                    'adverseEffects': 'N/A'
                },
            ]

    def growth_monitoring(self):
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        history_values = ChildHistory.before_date(child.child_health_case_id, self.date_)

        def _safe_last_val_access(key, index=-1):
            try:
                return history_values.get(key)[index][1]
            except IndexError:
                return 'N/A'

        ret = {
            'currentWeight': _safe_last_val_access('weight_child_history'),
            'growthMonitoringStatus': _safe_last_val_access('zscore_grading_wfa_history'),
            'previousGrowthMonitoringStatus': _safe_last_val_access('zscore_grading_wfa_history', -2),
            'underweight': _safe_last_val_access('zscore_grading_wfa_history') != 'green',
            'underweightStatus': _safe_last_val_access('zscore_grading_wfa_history'),
            'stunted': _safe_last_val_access('zscore_grading_hfa_history') != 'green',
            'stuntedStatus': _safe_last_val_access('zscore_grading_hfa_history'),
            'wasting': _safe_last_val_access('zscore_grading_wfh_history') != 'green',
            'wastingStatus': _safe_last_val_access('zscore_grading_wfh_history'),
            'nrcReferred': 'N/A',
            'referralDate': 'N/A',
        }

        return ret

    def weight_for_age_chart(self):
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        history_values = ChildHistory.before_date(child.child_health_case_id, self.date_)
        points = []

        for date_, weight in history_values['weight_child_history']:
            delta = relativedelta(date_, child.dob)
            months = delta.years * 12 + delta.months
            points.append({'x': months, 'y': weight})

        return points

    def height_for_age_chart(self):
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        history_values = ChildHistory.before_date(child.child_health_case_id, self.date_)
        points = []

        for date_, height in history_values['height_child_history']:
            delta = relativedelta(date_, child.dob)
            months = delta.years * 12 + delta.months
            points.append({'x': months, 'y': height})

        return points

    def weight_for_height_chart(self):
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        history_values = ChildHistory.before_date(child.child_health_case_id, self.date_)
        points_by_date = OrderedDict()

        for date_, weight in history_values['weight_child_history']:
            points_by_date[date_] = {'y': weight}

        for date_, height in history_values['height_child_history']:
            if date_ in points_by_date:
                points_by_date[date_]['x'] = height

        return list(points_by_date.values())


class PregnantWomanQueryHelper(object):
    def __init__(self, domain, person_case_id, date_):
        # TODO this needs to be changed to ccs_record id
        self.domain = domain
        self.person_case_id = person_case_id
        self.date_ = date_

    @classmethod
    def list(cls, domain, date_, location_filters, sort_column):
        location_query = ''
        if location_filters:
            location_query = [
                "woman.{loc} = %({loc})s".format(loc=loc) for loc in location_filters.keys()
            ]
            location_query = " AND ".join(location_query)
            location_query = location_query + " AND"

        query, params = """
            SELECT
                (woman.person_case_id) AS "id",
                woman.name AS "name",
                woman.dob AS "dob",
                ((%(start_date)s - "woman"."dob") / 30.417)::INT AS "age_in_months",
                EXTRACT('month' FROM age(ccs_record.preg_reg_date)) AS "pregMonth",
                ccs_record.hrp AS "highRiskPregnancy",
                ccs_record.num_anc_checkups AS "noOfAncCheckUps"
            FROM "{woman_table}" woman
            JOIN "{ccs_record_table}" ccs_record ON ccs_record.person_case_id=woman.person_case_id
            WHERE (
                woman.domain = %(domain)s AND
                {location_where}
                (daterange(%(start_date)s, %(end_date)s) && ANY(pregnant_ranges)) AND
                (ccs_record.add < %(start_date)s or ccs_record.add is NULL)
            ) ORDER BY {sort_col}
        """.format(
            location_where=location_query,
            woman_table=Woman._meta.db_table,
            ccs_record_table=CcsRecord._meta.db_table,
            sort_col=sort_column
        ), {
            'domain': domain,
            'start_date': date_,
            'end_date': date_ + relativedelta(months=1),
        }
        params.update(location_filters)
        db_alias = get_aaa_db_alias()
        with connections[db_alias].cursor() as cursor:
            cursor.execute(query, params)
            desc = cursor.description
            return [
                dict(zip([col[0] for col in desc], row))
                for row in cursor.fetchall()
            ]

    def pregnancy_details(self):
        data = CcsRecord.objects.extra(
            select={
                'weightOfPw': 'woman_weight_at_preg_reg',
                'dateOfRegistration': 'preg_reg_date',
            }
        ).values(
            'lmp', 'weightOfPw', 'dateOfRegistration', 'edd', 'add'
        ).get(domain=self.domain, person_case_id=self.person_case_id)
        # I think we should consider to add blood_group to the CcsRecord to don't have two queries
        data.update(
            Woman.objects.extra(
                select={
                    'bloodGroup': 'blood_group'
                }
            ).values('bloodGroup').get(
                domain=self.domain, person_case_id=self.person_case_id
            )
        )

        return data

    def pregnancy_risk(self):
        ret = {
            'riskPregnancy': 'N/A',
            'hrpSymptoms': 'N/A',  # not populated yet
            'referralDate': 'N/A',
            'referredOutFacilityType': 'N/A',
            'illnessHistory': 'N/A',
            'pastIllnessDetails': 'N/A',
        }

        ccs_record = (
            CcsRecord.objects
            .filter(domain=self.domain, person_case_id=self.person_case_id).first()
        )
        if ccs_record and ccs_record.hrp:
            ret['riskPregnancy'] = ccs_record.hrp

        bp_details = self._most_recent_bp_form_details(ccs_record)
        if bp_details:
            ret['referralDate'] = bp_details['date_referral'] or 'N/A'
            ret['referredOutFacilityType'] = bp_details['place_referral'] or 'N/A'

        add_preg_details = ccs_record.add_pregnancy_form_details()
        if add_preg_details:
            ret['illnessHistory'] = add_preg_details['past_illness'] or 'N/A'
            ret['pastIllnessDetails'] = add_preg_details['past_illness_details'] or 'N/A'

        return ret

    def consumables_disbursed(self):
        ccs_record = (
            CcsRecord.objects
            .filter(domain=self.domain, person_case_id=self.person_case_id).first()
        )
        thr = ccs_record.thr_form_details(self.date_)
        thr_disbursed = 'N/A'
        if thr:
            thr_disbursed = (
                (thr['thr_amount_1'] or 0)
                + (thr['thr_amount_2'] or 0)
                + (thr['thr_amount_3'] or 0)
                + (thr['thr_amount_4'] or 0)
                + (thr['thr_amount_5'] or 0)
                + (thr['thr_amount_6'] or 0)
                + (thr['thr_amount_7'] or 0)
                + (thr['thr_amount_8'] or 0)
            )

        deets = ccs_record.ccs_record_details()
        return {
            'ifaTablets': (deets['ifa_tablets_issued_pre'] or 0) + (deets['ifa_tablets_issued_post'] or 0),
            'thrDisbursed': thr_disbursed,
        }

    def immunization_counseling_details(self):
        ret = {
            'ttDoseOne': 'N/A',
            'ttDoseTwo': 'N/A',
            'ttBooster': 'N/A',
            'birthPreparednessVisitsByAsha': 'N/A',
            'birthPreparednessVisitsByAww': 'N/A',
            'counsellingOnMaternal': 'N/A',
            'counsellingOnEbf': 'N/A',
        }
        ccs_record = (
            CcsRecord.objects
            .filter(domain=self.domain, person_case_id=self.person_case_id).first()
        )
        tasks_case = ccs_record.task_case_details()
        if tasks_case:
            keys_to_col_names = (
                ('ttDoseOne', 'due_list_date_tt_1'),
                ('ttDoseTwo', 'due_list_date_tt_2'),
                ('ttBooster', 'due_list_date_tt_booster'),
            )
            for key, col_name in keys_to_col_names:
                if tasks_case[col_name] != date(1970, 1, 1):
                    ret[key] = tasks_case[col_name]

        bp_forms = self._bp_form_details(ccs_record)
        if bp_forms:
            ret['birthPreparednessVisitsByAsha'] = sum(1 for bp in bp_forms if bp['user_role'] == 'asha')
            ret['birthPreparednessVisitsByAww'] = sum(1 for bp in bp_forms if bp['user_role'] == 'aww')
            ret['counsellingOnMaternal'] = any(True for bp in bp_forms if bp['inform_danger_signs'] == 'yes')
            ret['counsellingOnEbf'] = any(True for bp in bp_forms if bp['immediate_breastfeeding'] == 'yes')

        return ret

    def abortion_details(self):
        ccs_record = (
            CcsRecord.objects
            .filter(domain=self.domain, person_case_id=self.person_case_id).first()
        )
        details = ccs_record.ccs_record_details()
        pregnancy_length = 'N/A'
        if details['date_abortion'] and details['lmp']:
            pregnancy_length = (details['date_abortion'] - details['lmp']).days
        return {
            'abortionDate': details['date_abortion'] or 'N/A',
            'abortionType': details['abortion_type'] or 'N/A',
            'abortionDays': pregnancy_length,
        }

    def maternal_death_details(self):
        ccs_record = (
            CcsRecord.objects
            .filter(domain=self.domain, person_case_id=self.person_case_id).first()
        )
        details = ccs_record.person_details()
        return {
            'maternalDeathOccurred': details['female_death_type'] is not None,
            'maternalDeathDate': details['date_death'] or 'N/A',
            'maternalDeathPlace': details['site_death'] or 'N/A',
            'authoritiesInformed': details['death_informed_authorities'] or 'N/A',
        }

    def delivery_details(self):
        ccs_record = (
            CcsRecord.objects
            .filter(domain=self.domain, person_case_id=self.person_case_id).first()
        )
        details = ccs_record.delivery_form_details()
        ccs_details = ccs_record.ccs_record_details()
        return {
            'dod': ccs_record.add or 'N/A',
            'timeOfDelivery': details.get('time_birth') or 'N/A',
            'placeOfDelivery': details.get('which_village') or 'N/A',
            'typeOfDelivery': details.get('delivery_nature') or 'N/A',
            'placeOfBirth': details.get('where_born') or 'N/A',
            'hospitalType': details.get('which_hospital') or 'N/A',
            'dateOfDischarge': details.get('discharge_date') or 'N/A',
            'timeOfDischarge': details.get('discharge_time') or 'N/A',
            'assistanceOfDelivery': details.get('who_assisted') or 'N/A',
            'deliveryComplications': ccs_details['complication_type'] or 'N/A',
            'complicationDetails': 'N/A',
        }

    def postnatal_care_details(self):
        ret = []
        ccs_record = (
            CcsRecord.objects
            .filter(domain=self.domain, person_case_id=self.person_case_id).first()
        )
        details = ccs_record.postnatal_care_form_details(self.date_)
        for detail in details:
            ret.append({
                'pncDate': detail['timeend'],
                'postpartumHeamorrhage': detail['bleeding'],
                'fever': detail['fever'],
                'convulsions': detail['convulsions'],
                'abdominalPain': detail['abdominal_pain'],
                'painfulUrination': detail['pain_urination'],
                'congestedBreasts': detail['congested'],
                'painfulNipples': detail['painful_nipples'],
                'otherBreastsIssues': detail['other_issues'],
                'managingBreastProblems': detail['counsel_breast'],
                'increasingFoodIntake': detail['counsel_increase_food_bf'],
                'possibleMaternalComplications': detail['counsel_maternal_comp'],
                'beneficiaryStartedEating': detail['eating_well'],
            })
        ret.reverse()  # postnatal_care_details returns in descending order, but we want ascending
        return ret

    def antenatal_care_details(self):
        ret = []
        ccs_record = (
            CcsRecord.objects
            .filter(domain=self.domain, person_case_id=self.person_case_id).first()
        )

        bp_forms = self._bp_form_details(ccs_record)
        bp_forms.reverse()
        for form in bp_forms:
            _ret = {
                'ancDate': form['date_task'],
                'ancLocation': form['anc_facility'],
                'pwWeight': form['anc_weight'],
                'bloodPressure': None,
                'hb': form['anc_hemoglobin'],
                'abdominalExamination': form['anc_abdominal_exam'],
                'abnormalitiesDetected': form['anc_abnormalities'],
            }
            if form['bp_sys'] and form['bp_dias']:
                _ret['bloodPressure'] = "{} / {}".format(form['bp_sys'], form['bp_dias'])
            ret.append(_ret)

        return ret

    def _most_recent_bp_form_details(self, ccs_record):
        bp_form_details = self._bp_form_details(ccs_record)
        if not bp_form_details:
            return {}
        return bp_form_details[0]

    def _bp_form_details(self, ccs_record):
        return ccs_record.birth_preparedness_form_details(self.date_)


class EligibleCoupleQueryHelper(object):
    ucr_table = 'reach-eligible_couple_forms'

    def __init__(self, domain, person_case_id, month_end):
        self.domain = domain
        self.person_case_id = person_case_id
        self.month_end = month_end

    @classmethod
    def _ucr_eligible_couple_table(cls, domain):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, cls.ucr_table)
        config, _ = get_datasource_config(doc_id, domain)
        return get_table_name(domain, config.table_id)

    @classmethod
    def list(cls, domain, date_, location_filters, sort_column):
        location_query = ''
        if location_filters:
            location_query = [
                "woman.{loc} = %({loc})s".format(loc=loc) for loc in location_filters.keys()
            ]
            location_query = " AND ".join(location_query)
            location_query = location_query + " AND"

        query, params = """
            SELECT
                woman.person_case_id AS "id",
                woman.name AS "name",
                woman.dob AS "dob",
                ((%(start_date)s - "woman"."dob") / 30.417)::INT AS "age_in_months",
                eligible_couple."currentFamilyPlanningMethod" AS "currentFamilyPlanningMethod",
                eligible_couple."adoptionDateOfFamilyPlaning" AS "adoptionDateOfFamilyPlaning"
            FROM "{woman_table}" woman
            LEFT JOIN (
                SELECT
                    "{eligible_couple_table}".person_case_id,
                    "{eligible_couple_table}".timeend::date AS "adoptionDateOfFamilyPlaning",
                    "{eligible_couple_table}".fp_current_method AS "currentFamilyPlanningMethod"
                FROM (
                    SELECT
                        person_case_id,
                        MAX(timeend) AS "timeend"
                    FROM "{eligible_couple_table}"
                    WHERE timeend <= %(end_date)s
                    GROUP BY person_case_id
                ) as last_eligible_couple
                INNER JOIN "{eligible_couple_table}" ON
                "{eligible_couple_table}".person_case_id=last_eligible_couple.person_case_id AND
                "{eligible_couple_table}".timeend=last_eligible_couple.timeend
            ) eligible_couple ON eligible_couple.person_case_id=woman.person_case_id
            WHERE (
                woman.domain = %(domain)s AND
                woman.marital_status = 'married' AND
                woman.migration_status IS DISTINCT FROM 'migrated' AND
                {location_where}
                dob BETWEEN %(dob_start_date)s AND %(dob_end_date)s AND
                (
                    pregnant_ranges IS NULL OR
                    NOT daterange(%(start_date)s, %(end_date)s) && ANY(pregnant_ranges)
                )
            ) ORDER BY {sort_col}
            """.format(
            location_where=location_query,
            woman_table=Woman._meta.db_table,
            eligible_couple_table=cls._ucr_eligible_couple_table(domain),
            sort_col=sort_column
        ), {
            'domain': domain,
            'dob_start_date': date_ - relativedelta(years=49),
            'dob_end_date': date_ - relativedelta(years=15),
            'start_date': date_,
            'end_date': date_ + relativedelta(months=1),
        }
        params.update(location_filters)
        db_alias = get_aaa_db_alias()
        with connections[db_alias].cursor() as cursor:
            cursor.execute(query, params)
            desc = cursor.description
            return [
                dict(zip([col[0] for col in desc], row))
                for row in cursor.fetchall()
            ]

    def eligible_couple_details(self):
        woman = Woman.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        children_by_sex = Child.objects.filter(mother_case_id=self.person_case_id).aggregate(
            male=Sum(Case(When(sex='M', then=1), output_field=IntegerField())),
            female=Sum(Case(When(sex='F', then=1), output_field=IntegerField())),
        )
        try:
            male_children_died = int(woman.num_male_children_died)
        except TypeError:
            male_children_died = 0
        try:
            female_children_died = int(woman.num_female_children_died)
        except TypeError:
            female_children_died = 0

        data = {
            'maleChildrenBorn': (children_by_sex['male'] or 0) + (male_children_died or 0),
            'femaleChildrenBorn': (children_by_sex['female'] or 0) + (female_children_died or 0),
            'maleChildrenAlive': (children_by_sex['male'] or 0),
            'femaleChildrenAlive': (children_by_sex['female'] or 0),
            'familyPlaningMethod': 'N/A',
            'familyPlanningMethodDate': 'N/A',
            'ashaVisit': 'N/A',
            'previousFamilyPlanningMethod': 'N/A',
            'preferredFamilyPlaningMethod': 'N/A',
        }

        ec_details = woman.eligible_couple_form_details(self.month_end)

        planning_methods = ec_details.get('fp_current_method_history')
        if planning_methods:
            # filter forms that don't update the current planning method (method[1] = '')
            planning_methods = [method for method in planning_methods if method[1]]

        if planning_methods:
            current_method = planning_methods[-1]
            data['familyPlaningMethod'] = current_method[1].replace("\'", '') if current_method[1] else 'N/A'
            data['familyPlanningMethodDate'] = force_to_datetime(
                current_method[0].replace("\'", '')
            ).date() if current_method[0] else 'N/A'
            if len(planning_methods) > 1:
                previous_method = planning_methods[-2][1].replace("\'", '') if planning_methods[-2][1] else 'N/A'
                data['previousFamilyPlanningMethod'] = previous_method

        preferred_methods = ec_details.get('fp_preferred_method_history')
        if preferred_methods:
            # filter forms that don't update the current preferred method (method[1] = '')
            preferred_methods = [method for method in preferred_methods if method[1]]

        if preferred_methods:
            data['preferredFamilyPlaningMethod'] = preferred_methods[-1][1] or 'N/A'

        if ec_details.get('family_planning_form_history'):
            data['ashaVisit'] = ec_details.get('family_planning_form_history')[-1]

        return data
