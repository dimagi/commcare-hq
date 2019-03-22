from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from django.test import override_settings
from django.test.testcases import TestCase
from mock import patch

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from custom.aaa.dbaccessors import ChildQueryHelper
from custom.aaa.models import Child


@override_settings(SERVER_ENVIRONMENT='icds')
class TestChildBeneficiarySections(TestCase):
    domain = 'reach-test'

    @classmethod
    def setUpClass(cls):
        super(TestChildBeneficiarySections, cls).setUpClass()
        Child.objects.create(
            domain=cls.domain,
            person_case_id='person_case_id',
            child_health_case_id='child_health_case_id',
            tasks_case_id='tasks_case',
            opened_on='2019-01-01',
            breastfed_within_first='yes',
            comp_feeding='yes',
            diet_diversity='yes',
            diet_quantity='no',
            birth_weight=3000,
            hand_wash='no',
            is_exclusive_breastfeeding='no',
            child_cried='no',
        )
        datasource_id = StaticDataSourceConfiguration.get_doc_id(cls.domain, 'reach-tasks_cases')
        datasource = StaticDataSourceConfiguration.by_id(datasource_id)
        cls.adapter = get_indicator_adapter(datasource)
        cls.adapter.build_table()
        immun_dates = {'1g_bcg': 32, '2g_opv_2': 85, '3g_rv_3': 11}
        with patch('corehq.apps.userreports.indicators.get_values_by_product', return_value=immun_dates):
            cls.adapter.save({
                '_id': 'tasks_case',
                'domain': cls.domain,
                'doc_type': "CommCareCase",
                'type': 'tasks',
            })

    @classmethod
    def tearDownClass(cls):
        cls.adapter.drop_table()
        Child.objects.all().delete()
        super(TestChildBeneficiarySections, cls).tearDownClass()

    def test_child_infant_details(self):
        self.assertEqual(
            ChildQueryHelper(self.domain, 'person_case_id').infant_details(),
            {
                'breastfeedingInitiated': 'yes',
                'dietDiversity': 'yes',
                'birthWeight': 3000,
                'dietQuantity': 'no',
                'breastFeeding': 'yes',
                'handwash': 'no',
                'exclusivelyBreastfed': 'no',
                'babyCried': 'no',
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
                {'vitaminName': 'BCG', 'date': date(1970, 2, 2), 'adverseEffects': 'N/A'},
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
                {'vitaminName': 'OPV - 2', 'date': date(1970, 3, 27), 'adverseEffects': 'N/A'},
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
                {'vitaminName': 'Rotavirus - 3', 'date': date(1970, 1, 12), 'adverseEffects': 'N/A'},
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
