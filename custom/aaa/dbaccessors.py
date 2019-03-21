from __future__ import absolute_import, unicode_literals

from dateutil.relativedelta import relativedelta

from custom.aaa.models import Child, ChildHistory


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
        return dict(
            currentWeight='N/A',
            nrcReferred='N/A',
            growthMonitoringStatus='N/A',
            referralDate='N/A',
            previousGrowthMonitoringStatus='N/A',
            underweight='N/A',
            underweightStatus='N/A',
            stunted='N/A',
            stuntedStatus='N/A',
            wasting='N/A',
            wastingStatus='N/A',
        )

    def weight_for_age_chart(self):
        child = Child.objects.get(person_case_id=self.person_case_id)
        points = {}
        try:
            child_history = ChildHistory.objects.get(child_health_case_id=child.child_health_case_id)
        except ChildHistory.DoesNotExist:
            pass
        else:
            for recorded_weight in child_history.weight_child_history:
                month = relativedelta(recorded_weight[0], child.dob).months
                points[month] = recorded_weight[1]

        return points

    def height_for_age_chart(self):
        child = Child.objects.get(person_case_id=self.person_case_id)
        points = {}
        try:
            child_history = ChildHistory.objects.get(child_health_case_id=child.child_health_case_id)
        except ChildHistory.DoesNotExist:
            pass
        else:
            for recorded_height in child_history.height_child_history:
                month = relativedelta(recorded_height[0], child.dob).months
                points[month] = recorded_height[1]

        return points

    def weight_for_height_chart(self):
        child = Child.objects.get(person_case_id=self.person_case_id)
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
