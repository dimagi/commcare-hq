from __future__ import absolute_import, unicode_literals

from dateutil.relativedelta import relativedelta
from django.db.models import Case, IntegerField, Sum, When

from custom.aaa.models import (
    CcsRecord,
    Child,
    ChildHistory,
    Woman,
    WomanHistory,
)


class ChildQueryHelper(object):
    def __init__(self, domain, person_case_id):
        self.domain = domain
        self.person_case_id = person_case_id

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
        # TODO update when CcsRecord will have properties from PNC form
        return [{
            'pncDate': 'N/A',
            'breastfeeding': 'N/A',
            'skinToSkinContact': 'N/A',
            'wrappedUpAdequately': 'N/A',
            'awakeActive': 'N/A',
        }]

    def vaccination_details(self, period):
        if period == 'atBirth':
            return [
                {'vitaminName': 'BCG', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Hepatitis B - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'OPV - 0', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ]
        elif period == 'sixWeek':
            return [
                {'vitaminName': 'OPV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Fractional IPV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'PCV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ]
        elif period == 'tenWeek':
            return [
                {'vitaminName': 'OPV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ]
        elif period == 'fourteenWeek':
            return [
                {'vitaminName': 'OPV - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Fractional IPV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'PCV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ]
        elif period == 'nineTwelveMonths':
            return [
                {'vitaminName': 'PCV Booster', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Measles - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'JE - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ]
        elif period == 'sixTeenTwentyFourMonth':
            return [
                {'vitaminName': 'DPT Booster - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Measles - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'OPV Booster', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'JE - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ]
        elif period == 'twentyTwoSeventyTwoMonth':
            return [
                {'vitaminName': 'Vit. A - 4', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 5', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 6', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 7', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 8', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 9', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'DPT Booster - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ]

    def growth_monitoring(self):
        return {
            'currentWeight': 'N/A',
            'nrcReferred': 'N/A',
            'growthMonitoringStatus': 'N/A',
            'referralDate': 'N/A',
            'previousGrowthMonitoringStatus': 'N/A',
            'underweight': 'N/A',
            'underweightStatus': 'N/A',
            'stunted': 'N/A',
            'stuntedStatus': 'N/A',
            'wasting': 'N/A',
            'wastingStatus': 'N/A',
        }

    def weight_for_age_chart(self):
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        points = []
        try:
            child_history = ChildHistory.objects.get(child_health_case_id=child.child_health_case_id)
        except ChildHistory.DoesNotExist:
            pass
        else:
            for recorded_weight in child_history.weight_child_history:
                month = relativedelta(recorded_weight[0], child.dob).months
                points.append({'x': month, 'y': recorded_weight[1]})

        return points

    def height_for_age_chart(self):
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        points = []
        try:
            child_history = ChildHistory.objects.get(child_health_case_id=child.child_health_case_id)
        except ChildHistory.DoesNotExist:
            pass
        else:
            for recorded_height in child_history.height_child_history:
                month = relativedelta(recorded_height[0], child.dob).months
                points.append({'x': month, 'y': recorded_height[1]})

        return points

    def weight_for_height_chart(self):
        child = Child.objects.get(domain=self.domain, person_case_id=self.person_case_id)
        points = {}
        try:
            child_history = ChildHistory.objects.get(child_health_case_id=child.child_health_case_id)
        except ChildHistory.DoesNotExist:
            pass
        else:
            for recorded_weight in child_history.weight_child_history:
                month = relativedelta(recorded_weight[0], child.dob).months
                points.update({month: dict(x=recorded_weight[1])})
            for recorded_height in child_history.height_child_history:
                month = relativedelta(recorded_height[0], child.dob).months
                if month in points:
                    points[month].update(dict(y=recorded_height[1]))
                else:
                    points.update({month: dict(y=recorded_height[1])})

        return [point for point in points.values() if 'x' in point and 'y' in point]


class PregnantWomanQueryHelper(object):
    def __init__(self, domain, person_case_id):
        # TODO this needs to be changed to ccs_record id
        self.domain = domain
        self.person_case_id = person_case_id

    def pregnancy_details(self):
        data = CcsRecord.objects.extra(
            select={
                'dateOfLmp': 'lmp',
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
        return {
            'riskPregnancy': 'N/A',
            'referralDate': 'N/A',
            'hrpSymptoms': 'N/A',
            'illnessHistory': 'N/A',
            'referredOutFacilityType': 'N/A',
            'pastIllnessDetails': 'N/A',
        }

    def consumables_disbursed(self):
        return {
            'ifaTablets': 'N/A',
            'thrDisbursed': 'N/A',
        }

    def immunization_counseling_details(self):
        return {
            'ttDoseOne': 'N/A',
            'ttDoseTwo': 'N/A',
            'ttBooster': 'N/A',
            'birthPreparednessVisitsByAsha': 'N/A',
            'birthPreparednessVisitsByAww': 'N/A',
            'counsellingOnMaternal': 'N/A',
            'counsellingOnEbf': 'N/A',
        }

    def abortion_details(self):
        return {
            'abortionDate': 'N/A',
            'abortionType': 'N/A',
            'abortionDays': 'N/A',
        }

    def maternal_death_details(self):
        return {
            'maternalDeathOccurred': 'N/A',
            'maternalDeathPlace': 'N/A',
            'maternalDeathDate': 'N/A',
            'authoritiesInformed': 'N/A',
        }

    def delivery_details(self):
        return {
            'dod': 'N/A',
            'assistanceOfDelivery': 'N/A',
            'timeOfDelivery': 'N/A',
            'dateOfDischarge': 'N/A',
            'typeOfDelivery': 'N/A',
            'timeOfDischarge': 'N/A',
            'placeOfBirth': 'N/A',
            'deliveryComplications': 'N/A',
            'placeOfDelivery': 'N/A',
            'complicationDetails': 'N/A',
            'hospitalType': 'N/A',
        }

    def postnatal_care_details(self):
        return [{
            'pncDate': '2019-08-20',
            'postpartumHeamorrhage': 0,
            'fever': 1,
            'convulsions': 0,
            'abdominalPain': 0,
            'painfulUrination': 0,
            'congestedBreasts': 1,
            'painfulNipples': 0,
            'otherBreastsIssues': 0,
            'managingBreastProblems': 0,
            'increasingFoodIntake': 1,
            'possibleMaternalComplications': 1,
            'beneficiaryStartedEating': 0,
        }]

    def antenatal_care_details(self):
        return [{
            'ancDate': 'N/A',
            'ancLocation': 'N/A',
            'pwWeight': 'N/A',
            'bloodPressure': 'N/A',
            'hb': 'N/A',
            'abdominalExamination': 'N/A',
            'abnormalitiesDetected': 'N/A',
        }]


class EligibleCoupleQueryHelper(object):
    def __init__(self, domain, person_case_id, month_end):
        self.domain = domain
        self.person_case_id = person_case_id
        self.month_end = month_end

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
            'maleChildrenBorn': max(0, children_by_sex['male']) + max(0, male_children_died),
            'femaleChildrenBorn': max(0, children_by_sex['female']) + max(0, female_children_died),
            'maleChildrenAlive': max(0, children_by_sex['male']),
            'femaleChildrenAlive': max(0, children_by_sex['female']),
            'familyPlaningMethod': 'N/A',
            'familyPlanningMethodDate': 'N/A',
            'ashaVisit': 'N/A',
            'previousFamilyPlanningMethod': 'N/A',
            'preferredFamilyPlaningMethod': 'N/A',
        }

        history = WomanHistory.objects.filter(person_case_id=self.person_case_id).first()
        safe_history = {}
        if history:
            safe_history = history.date_filter(self.month_end)

        planning_methods = safe_history.get('family_planning_method')
        if planning_methods:
            data['familyPlaningMethod'] = planning_methods[-1][1]
            data['familyPlanningMethodDate'] = planning_methods[-1][0]
            if len(planning_methods) > 1:
                data['previousFamilyPlanningMethod'] = planning_methods[-2][1]

        preferred_methods = safe_history.get('preferred_family_planning_methods')
        if preferred_methods:
            data['preferredFamilyPlaningMethod'] = preferred_methods[-1][1]

        data['ashaVisit'] = safe_history.get('last_family_planning_form') or 'N/A'

        return data
