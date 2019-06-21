from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from django.test import override_settings
from django.test.testcases import TestCase
from mock import patch

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from custom.aaa.dbaccessors import ChildQueryHelper
from custom.aaa.models import Child, ChildHistory


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
            dob='2017-01-01',
            breastfed_within_first='yes',
            comp_feeding='yes',
            diet_diversity='yes',
            diet_quantity='no',
            birth_weight=3000,
            hand_wash='no',
            is_exclusive_breastfeeding='no',
            child_cried='no',
        )
        ChildHistory.objects.create(
            child_health_case_id='child_health_case_id',
            weight_child_history=[
                ['2019-01-01', '8'],
                ['2019-02-01', '10'],
                ['2019-04-01', '12'],
            ],
            height_child_history=[
                ['2019-01-01', '72'],
                ['2019-02-01', '87'],
                ['2019-04-01', '105'],
            ],
            zscore_grading_wfa_history=[
                ['2019-01-01', 'green'],
                ['2019-02-01', 'yellow'],
                ['2019-04-01', 'red'],
            ],
            zscore_grading_hfa_history=[
                ['2019-01-01', 'green'],
                ['2019-02-01', 'yellow'],
                ['2019-04-01', 'red'],
            ],
            zscore_grading_wfh_history=[
                ['2019-01-01', 'green'],
                ['2019-02-01', 'yellow'],
                ['2019-04-01', 'red'],
            ],
        )
        cls.adapters = []
        immun_adapter = cls._init_table('reach-tasks_cases')
        immun_dates = {'1g_bcg': 32, '2g_opv_2': 85, '3g_rv_3': 11}
        with patch('corehq.apps.userreports.indicators.get_values_by_product', return_value=immun_dates):
            immun_adapter.save({
                '_id': 'tasks_case',
                'domain': cls.domain,
                'doc_type': "CommCareCase",
                'type': 'tasks',
                'owner_id': '-',
            })
        pnc_adapter = cls._init_table('reach-postnatal_care')
        pnc_adapter.save({
            '_id': 'pnc_form',
            'domain': cls.domain,
            'doc_type': "XFormInstance",
            'xmlns': 'http://openrosa.org/formdesigner/D4A7ABD2-A7B8-431B-A88B-38245173B0AE',
            'form': {
                "child": {
                    "item": [
                        {'child_health_case_id': 'child_health_case_id', 'skin_to_skin': 'yes', 'wrapped': 'yes'},
                        {
                            'child_health_case_id': 'child_health_case_id',
                            'skin_to_skin': 'yes',
                            'breastfeeding_well': 'yes'
                        },
                    ],
                },
                "meta": {"timeEnd": "2019-01-01T10:37:00Z"},
            },
        })

    @classmethod
    def tearDownClass(cls):
        for adapter in cls.adapters:
            adapter.drop_table()
        ChildHistory.objects.all().delete()
        Child.objects.all().delete()
        super(TestChildBeneficiarySections, cls).tearDownClass()

    @classmethod
    def _init_table(cls, data_source_id):
        datasource_id = StaticDataSourceConfiguration.get_doc_id(cls.domain, data_source_id)
        datasource = StaticDataSourceConfiguration.by_id(datasource_id)
        adapter = get_indicator_adapter(datasource)
        adapter.build_table()
        cls.adapters.append(adapter)
        return adapter

    def _helper(self, person_case_id='person_case_id'):
        return ChildQueryHelper(self.domain, person_case_id, date(2019, 3, 1))

    def test_child_infant_details(self):
        self.assertEqual(
            self._helper().infant_details(),
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
            self._helper().postnatal_care_details(),
            [{
                'pncDate': date(2019, 1, 1),
                'breastfeeding': 'N/A',
                'skinToSkinContact': 'yes',
                'wrappedUpAdequately': 'yes',
                'awakeActive': 'N/A',
            }, {
                'pncDate': date(2019, 1, 1),
                'breastfeeding': 'yes',
                'skinToSkinContact': 'yes',
                'wrappedUpAdequately': 'N/A',
                'awakeActive': 'N/A',
            }])

    def test_vaccination_details_at_birth(self):
        self.assertEqual(
            self._helper().vaccination_details('atBirth'),
            [
                {'vitaminName': 'BCG', 'date': date(1970, 2, 2), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Hepatitis B - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'OPV - 0', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_six_week(self):
        self.assertEqual(
            self._helper().vaccination_details('sixWeek'),
            [
                {'vitaminName': 'OPV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Fractional IPV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'PCV - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_ten_week(self):
        self.assertEqual(
            self._helper().vaccination_details('tenWeek'),
            [
                {'vitaminName': 'OPV - 2', 'date': date(1970, 3, 27), 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_fourteen_week(self):
        self.assertEqual(
            self._helper().vaccination_details('fourteenWeek'),
            [
                {'vitaminName': 'OPV - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Pentavalent - 3', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Fractional IPV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Rotavirus - 3', 'date': date(1970, 1, 12), 'adverseEffects': 'N/A'},
                {'vitaminName': 'PCV - 2', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_nine_twelve_months(self):
        self.assertEqual(
            self._helper().vaccination_details('nineTwelveMonths'),
            [
                {'vitaminName': 'PCV Booster', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Vit. A - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'Measles - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
                {'vitaminName': 'JE - 1', 'date': 'N/A', 'adverseEffects': 'N/A'},
            ])

    def test_vaccination_details_sixteen_twenty_four_month(self):
        self.assertEqual(
            self._helper().vaccination_details('sixTeenTwentyFourMonth'),
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
            self._helper().vaccination_details('twentyTwoSeventyTwoMonth'),
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
            self._helper().growth_monitoring(),
            {
                'currentWeight': '10',
                'growthMonitoringStatus': 'yellow',
                'previousGrowthMonitoringStatus': 'green',
                'underweight': True,
                'underweightStatus': 'yellow',
                'stunted': True,
                'stuntedStatus': 'yellow',
                'wasting': True,
                'wastingStatus': 'yellow',
                'nrcReferred': 'N/A',
                'referralDate': 'N/A',
            })

    def test_growth_monitoring_no_history(self):
        child = Child.objects.create(
            domain=self.domain,
            child_health_case_id='no_history',
            person_case_id='no_history',
            opened_on='2019-01-01',
        )
        self.addCleanup(child.delete)
        self.assertEqual(
            self._helper(person_case_id='no_history').growth_monitoring(),
            {
                'currentWeight': 'N/A',
                'growthMonitoringStatus': 'N/A',
                'previousGrowthMonitoringStatus': 'N/A',
                'underweight': True,
                'underweightStatus': 'N/A',
                'stunted': True,
                'stuntedStatus': 'N/A',
                'wasting': True,
                'wastingStatus': 'N/A',
                'nrcReferred': 'N/A',
                'referralDate': 'N/A',
            })

    def test_weight_for_age_chart(self):
        self.assertEqual(
            self._helper().weight_for_age_chart(),
            [{'x': 24, 'y': '8'}, {'x': 25, 'y': '10'}]
        )

    def test_weight_for_age_no_history(self):
        child = Child.objects.create(
            domain=self.domain,
            child_health_case_id='no_history',
            person_case_id='no_history',
            opened_on='2019-01-01',
        )
        self.addCleanup(child.delete)
        self.assertEqual(self._helper(person_case_id='no_history').weight_for_age_chart(), [])

    def test_height_for_age_chart(self):
        self.assertEqual(
            self._helper().height_for_age_chart(),
            [{'x': 24, 'y': '72'}, {'x': 25, 'y': '87'}]
        )

    def test_height_for_age_no_history(self):
        child = Child.objects.create(
            domain=self.domain,
            child_health_case_id='no_history',
            person_case_id='no_history',
            opened_on='2019-01-01',
        )
        self.addCleanup(child.delete)
        self.assertEqual(self._helper(person_case_id='no_history').height_for_age_chart(), [])

    def test_weight_for_height_chart(self):
        self.assertEqual(
            self._helper().weight_for_height_chart(),
            [{'x': '72', 'y': '8'}, {'x': '87', 'y': '10'}]
        )

    def test_weight_for_height_no_history(self):
        child = Child.objects.create(
            domain=self.domain,
            child_health_case_id='no_history',
            person_case_id='no_history',
            opened_on='2019-01-01',
        )
        self.addCleanup(child.delete)
        self.assertEqual(self._helper(person_case_id='no_history').weight_for_height_chart(), [])


class TestChildBeneficiaryList(TestCase):
    domain = 'reach-test'

    def tearDown(self):
        Child.objects.all().delete()
        super(TestChildBeneficiaryList, self).tearDown()

    def _create_child(self, dob):
        Child.objects.create(child_health_case_id='_id', domain=self.domain, dob=dob, opened_on='2019-01-01')

    def test_six_year_old(self):
        self._create_child('2013-01-01')
        self.assertEqual(ChildQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 0)

    def test_five_year_old(self):
        self._create_child('2014-12-01')
        self.assertEqual(ChildQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 1)

    def test_future_child(self):
        self._create_child('2019-12-01')
        self.assertEqual(ChildQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 0)

    def test_newborn(self):
        self._create_child(date(2019, 2, 28))
        self.assertEqual(ChildQueryHelper.list(self.domain, date(2019, 3, 1), {}, 'id').count(), 1)
