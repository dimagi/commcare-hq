from __future__ import absolute_import
from __future__ import unicode_literals

from django.test.testcases import TestCase

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
        )
        CcsRecord.objects.create(
            domain=cls.domain,
            person_case_id='person_case_id',
            ccs_record_case_id='ccs_record_case_id',
            opened_on='2019-01-01',
        )

    @classmethod
    def tearDownClass(cls):
        CcsRecord.objects.all().delete()
        Woman.objects.all().delete()
        super(TestPregnantWomanBeneficiarySections, cls).tearDownClass()

    def test_pregnancy_details(self):
        self.assertEqual(
            PregnantWomanQueryHelper(self.domain, 'person_case_id').pregnancy_details(),
            {
                'lmp': None,
                'weightOfPw': None,
                'dateOfRegistration': None,
                'edd': None,
                'add': None,
                'bloodGroup': None,
            })

    def test_pregnancy_risk(self):
        self.assertEqual(
            PregnantWomanQueryHelper(self.domain, 'person_case_id').pregnancy_risk(),
            {
                'riskPregnancy': 'N/A',
                'referralDate': 'N/A',
                'hrpSymptoms': 'N/A',
                'illnessHistory': 'N/A',
                'referredOutFacilityType': 'N/A',
                'pastIllnessDetails': 'N/A',
            })

    def test_consumables_disbursed(self):
        self.assertEqual(
            PregnantWomanQueryHelper(self.domain, 'person_case_id').consumables_disbursed(),
            {
                'ifaTablets': 'N/A',
                'thrDisbursed': 'N/A',
            })

    def test_immunization_counseling_details(self):
        self.assertEqual(
            PregnantWomanQueryHelper(self.domain, 'person_case_id').immunization_counseling_details(),
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
            PregnantWomanQueryHelper(self.domain, 'person_case_id').abortion_details(),
            {
                'abortionDate': 'N/A',
                'abortionType': 'N/A',
                'abortionDays': 'N/A',
            })

    def test_maternal_death_details(self):
        self.assertEqual(
            PregnantWomanQueryHelper(self.domain, 'person_case_id').maternal_death_details(),
            {
                'maternalDeathOccurred': 'N/A',
                'maternalDeathPlace': 'N/A',
                'maternalDeathDate': 'N/A',
                'authoritiesInformed': 'N/A',
            })

    def test_delivery_details(self):
        self.assertEqual(
            PregnantWomanQueryHelper(self.domain, 'person_case_id').delivery_details(),
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
            PregnantWomanQueryHelper(self.domain, 'person_case_id').postnatal_care_details(),
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
            PregnantWomanQueryHelper(self.domain, 'person_case_id').antenatal_care_details(),
            [{
                'ancDate': 'N/A',
                'ancLocation': 'N/A',
                'pwWeight': 'N/A',
                'bloodPressure': 'N/A',
                'hb': 'N/A',
                'abdominalExamination': 'N/A',
                'abnormalitiesDetected': 'N/A',
            }])
