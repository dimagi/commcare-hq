from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from django.test.testcases import TestCase

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from custom.aaa.dbaccessors import PregnantWomanQueryHelper
from custom.aaa.models import CcsRecord, Woman


class TestPregnantWomanBeneficiarySections(TestCase):
    domain = 'reach-test'

    @classmethod
    def setUpClass(cls):
        super(TestPregnantWomanBeneficiarySections, cls).setUpClass()
        Woman.objects.create(
            domain=cls.domain,
            person_case_id='person_case_id',
            opened_on='2019-01-01',
            blood_group='b_pos',
        )
        CcsRecord.objects.create(
            domain=cls.domain,
            person_case_id='person_case_id',
            ccs_record_case_id='ccs_record_case_id',
            opened_on='2019-01-01',
            hrp='yes',
            lmp='2018-12-03',
            woman_weight_at_preg_reg=54,
            preg_reg_date='2018-12-31',
            edd='2019-07-27',
            add='2019-07-31',
        )
        datasource_id = StaticDataSourceConfiguration.get_doc_id(cls.domain, 'reach-add_pregnancy')
        datasource = StaticDataSourceConfiguration.by_id(datasource_id)
        add_preg_adapter = get_indicator_adapter(datasource)
        add_preg_adapter.build_table()
        add_preg_adapter.save({
            '_id': 'bp_form',
            'domain': cls.domain,
            'doc_type': "XFormInstance",
            'xmlns': 'http://openrosa.org/formdesigner/362f76b242d0cfdcec66776f9586dc3620e9cce5',
            'form': {
                "case_open_ccs_record_1": {"case": {"@case_id": 'ccs_record_case_id'}},
                "pregnancy": {"past_illness": "malaria", "past_illness_details": "took_malarone"},
                "meta": {"timeEnd": "2019-01-01T10:37:00Z"},
            },
        })
        datasource_id = StaticDataSourceConfiguration.get_doc_id(cls.domain, 'reach-birth_preparedness')
        datasource = StaticDataSourceConfiguration.by_id(datasource_id)
        bp_adapter = get_indicator_adapter(datasource)
        bp_adapter.build_table()
        bp_adapter.save({
            '_id': 'bp_form',
            'domain': cls.domain,
            'doc_type': "XFormInstance",
            'xmlns': 'http://openrosa.org/formdesigner/2864010F-B1B1-4711-8C59-D5B2B81D65DB',
            'form': {
                "case_load_ccs_record0": {"case": {"@case_id": 'ccs_record_case_id'}},
                "date_referral": "2018-12-07",
                "place_referral": "chc",
                "meta": {"timeEnd": "2019-01-01T10:37:00Z"},
            },
        })
        cls.adapters = [
            add_preg_adapter,
            bp_adapter,
        ]

    @classmethod
    def tearDownClass(cls):
        for adapter in cls.adapters:
            adapter.drop_table()
        CcsRecord.objects.all().delete()
        Woman.objects.all().delete()
        super(TestPregnantWomanBeneficiarySections, cls).tearDownClass()

    @property
    def _helper(self):
        return PregnantWomanQueryHelper(self.domain, 'person_case_id', date(2019, 2, 1))

    def test_pregnancy_details(self):
        self.assertEqual(
            self._helper.pregnancy_details(),
            {
                'lmp': date(2018, 12, 03),
                'weightOfPw': 54,
                'dateOfRegistration': date(2018, 12, 31),
                'edd': date(2019, 7, 27),
                'add': date(2019, 7, 31),
                'bloodGroup': 'b_pos',
            })

    def test_pregnancy_risk(self):
        self.assertEqual(
            self._helper.pregnancy_risk(),
            {
                'riskPregnancy': 'yes',
                'referralDate': date(2018, 12, 7),
                'referredOutFacilityType': 'chc',
                'hrpSymptoms': 'N/A',
                'illnessHistory': 'malaria',
                'pastIllnessDetails': 'took_malarone',
            })

    def test_consumables_disbursed(self):
        self.assertEqual(
            self._helper.consumables_disbursed(),
            {
                'ifaTablets': 'N/A',
                'thrDisbursed': 'N/A',
            })

    def test_immunization_counseling_details(self):
        self.assertEqual(
            self._helper.immunization_counseling_details(),
            {
                'ttDoseOne': 'N/A',
                'ttDoseTwo': 'N/A',
                'ttBooster': 'N/A',
                'birthPreparednessVisitsByAsha': 'N/A',
                'birthPreparednessVisitsByAww': 'N/A',
                'counsellingOnMaternal': 'N/A',
                'counsellingOnEbf': 'N/A',
            })

    def test_abortion_details(self):
        self.assertEqual(
            self._helper.abortion_details(),
            {
                'abortionDate': 'N/A',
                'abortionType': 'N/A',
                'abortionDays': 'N/A',
            })

    def test_maternal_death_details(self):
        self.assertEqual(
            self._helper.maternal_death_details(),
            {
                'maternalDeathOccurred': 'N/A',
                'maternalDeathPlace': 'N/A',
                'maternalDeathDate': 'N/A',
                'authoritiesInformed': 'N/A',
            })

    def test_delivery_details(self):
        self.assertEqual(
            self._helper.delivery_details(),
            {
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
            })

    def test_postnatal_care_details(self):
        self.assertEqual(
            self._helper.postnatal_care_details(),
            [{
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
            }])

    def test_antenatal_care_details(self):
        self.assertEqual(
            self._helper.antenatal_care_details(),
            [{
                'ancDate': 'N/A',
                'ancLocation': 'N/A',
                'pwWeight': 'N/A',
                'bloodPressure': 'N/A',
                'hb': 'N/A',
                'abdominalExamination': 'N/A',
                'abnormalitiesDetected': 'N/A',
            }])
