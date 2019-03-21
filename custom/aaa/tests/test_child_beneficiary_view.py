from __future__ import absolute_import
from __future__ import unicode_literals

from django.test.testcases import TestCase

from custom.aaa.dbaccessors import ChildQueryHelper
from custom.aaa.models import Child


class TestChildBeneficiarySections(TestCase):
    domain = 'reach-test'

    @classmethod
    def setUpClass(cls):
        super(TestChildBeneficiarySections, cls).setUpClass()
        Child.objects.create(
            domain=cls.domain,
            person_case_id='person_case_id',
            child_health_case_id='child_health_case_id',
            opened_on='2019-01-01'
        )

    @classmethod
    def tearDownClass(cls):
        Child.objects.all().delete()
        super(TestChildBeneficiarySections, cls).tearDownClass()

    def test_child_infant_details(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').infant_details(),
            {
                'breastfeedingInitiated': None,
                'dietDiversity': None,
                'birthWeight': None,
                'dietQuantity': None,
                'breastFeeding': None,
                'handwash': None,
                'exclusivelyBreastfed': None,
                'babyCried': None,
                'pregnancyLength': 'N/A',
            })

    def test_postnatal_care_details(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').postnatal_care_details(),
            [{
                'pncDate': 'N/A',
                'breastfeeding': 'N/A',
                'skinToSkinContact': 'N/A',
                'wrappedUpAdequately': 'N/A',
                'awakeActive': 'N/A',
            }])

    def test_vaccination_details_at_birth(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').vaccination_details('atBirth'),
            [
                {'vitaminName': 'BCG', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Hepatitis B - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'OPV - 0', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_six_week(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').vaccination_details('sixWeek'),
            [
                {'vitaminName': 'OPV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Fractional IPV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'PCV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_ten_week(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').vaccination_details('tenWeek'),
            [
                {'vitaminName': 'OPV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_fourteen_week(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').vaccination_details('fourteenWeek'),
            [
                {'vitaminName': 'OPV - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Fractional IPV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'PCV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_nine_twelve_months(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').vaccination_details('nineTwelveMonths'),
            [
                {'vitaminName': 'PCV Booster', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Measles - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'JE - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_sixteen_twenty_four_month(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').vaccination_details('sixTeenTwentyFourMonth'),
            [
                {'vitaminName': 'DPT Booster - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Measles - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'OPV Booster', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'JE - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_twenty_two_seventy_two_month(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').vaccination_details('twentyTwoSeventyTwoMonth'),
            [
                {'vitaminName': 'Vit. A - 4', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 5', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 6', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 7', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 8', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 9', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'DPT Booster - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_growth_monitoring(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').growth_monitoring(),
            {
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
            })

    def test_weight_for_age_chart(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').weight_for_age_chart(),
            []
        )

    def test_height_for_age_chart(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').height_for_age_chart(),
            []
        )

    def test_weight_for_height_chart(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').weight_for_height_chart(),
            []
        )
