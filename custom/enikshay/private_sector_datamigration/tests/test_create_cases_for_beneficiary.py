from collections import OrderedDict
from datetime import datetime

from django.core.management import call_command
from django.test import TestCase, override_settings

from mock import patch

from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID
from casexml.apps.case.sharedmodels import CommCareCaseIndex

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.private_sector_datamigration.models import (
    Adherence,
    Agency,
    Beneficiary,
    EpisodePrescription,
    LabTest,
    Episode,
    UserDetail,
)
from custom.enikshay.tests.utils import ENikshayLocationStructureMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestCreateCasesByBeneficiary(ENikshayLocationStructureMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'test_domain'
        super(TestCreateCasesByBeneficiary, cls).setUpClass()
        cls.beneficiary = Beneficiary.objects.create(
            addressLineOne='585 Mass Ave',
            addressLineTwo='Suite 4',
            age=25,
            caseId='3',
            caseStatus='patient',
            creationDate=datetime(2017, 1, 1),
            dateOfRegn=datetime(2017, 4, 17),
            dob=datetime(1992, 1, 2),
            emergencyContactNo='1234567890',
            firstName='Nick',
            gender='4',
            identificationNumber='98765',
            identificationTypeId='16',
            isActive=True,
            lastName='P',
            organisationId=2,
            phoneNumber='5432109876',
            referredQP='org123'
        )
        cls.case_accessor = CaseAccessors(cls.domain)

        cls.agency = Agency.objects.create(
            agencyId=1,
            creationDate=datetime(2017, 5, 1),
            dateOfRegn=datetime(2017, 5, 1),
            modificationDate=datetime(2017, 5, 1),
            nikshayId='123456',
            organisationId=2,
            parentAgencyId=3,
            subOrganisationId=4,
        )
        UserDetail.objects.create(
            id=0,
            agencyId=cls.agency.agencyId,
            isPrimary=True,
            motechUserName='org123',
            organisationId=2,
            passwordResetFlag=False,
            pincode=3,
            subOrganisationId=4,
            userId=5,
            valid=True,
        )

    def setUp(self):
        super(TestCreateCasesByBeneficiary, self).setUp()

        self.pcp.site_code = self.agency.nikshayId
        self.pcp.save()

    @patch('custom.enikshay.private_sector_datamigration.factory.datetime')
    def test_create_cases_for_beneficiary(self, mock_datetime):
        mock_datetime.utcnow.return_value = datetime(2016, 9, 8, 1, 2, 3, 4123)

        Episode.objects.create(
            adherenceScore=0.5,
            alertFrequencyId=2,
            beneficiaryID=self.beneficiary,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            episodeDisplayID=3,
            episodeID=6,
            extraPulmonary='Abdomen',
            hiv='Negative',
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            newOrRetreatment='New',
            nikshayID='02139-02215',
            patientWeight=50,
            rxStartDate=datetime(2017, 4, 19),
            site='Extrapulmonary',
            unknownAdherencePct=0.9,
            unresolvedMissedDosesPct=0.1,
        )
        call_command('create_cases_by_beneficiary', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertFalse(person_case.closed)
        self.assertIsNone(person_case.external_id)
        self.assertEqual(person_case.name, 'Nick P')
        self.assertEqual(person_case.owner_id, self.pcp.location_id)
        self.assertEqual(person_case.dynamic_case_properties(), OrderedDict([
            ('aadhaar_number', '98765'),
            ('age', '25'),
            ('age_entered', '25'),
            ('current_address', '585 Mass Ave, Suite 4'),
            ('current_episode_type', 'confirmed_tb'),
            ('current_patient_type_choice', 'new'),
            ('dataset', 'real'),
            ('dob', '1992-01-02'),
            ('dob_known', 'yes'),
            ('enrolled_in_private', 'true'),
            ('first_name', 'Nick'),
            ('hiv_status', 'non_reactive'),
            ('is_active', 'yes'),
            ('last_name', 'P'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
            ('occupation', ''),
            ('phone_number', '5432109876'),
            ('secondary_contact_phone_number', '1234567890'),
            ('sex', 'male'),
        ]))
        self.assertEqual(len(person_case.xform_ids), 1)

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(len(occurrence_case_ids), 1)
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertFalse(occurrence_case.closed)
        self.assertIsNone(occurrence_case.external_id)
        self.assertEqual(occurrence_case.name, 'Occurrence #1')
        self.assertEqual(occurrence_case.owner_id, '-')
        self.assertEqual(occurrence_case.dynamic_case_properties(), OrderedDict([
            ('current_episode_type', 'confirmed_tb'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
            ('occurrence_id', '20160908010203004')
        ]))
        self.assertEqual(len(occurrence_case.indices), 1)
        self._assertIndexEqual(
            occurrence_case.indices[0],
            CommCareCaseIndex(
                identifier='host',
                referenced_type='person',
                referenced_id=person_case.get_id,
                relationship='extension',
            )
        )
        self.assertEqual(len(occurrence_case.xform_ids), 1)

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertFalse(episode_case.closed)
        self.assertEqual(episode_case.external_id, '02139-02215')
        self.assertEqual(episode_case.name, 'Episode #1: Confirmed TB (Patient)')
        self.assertEqual(episode_case.opened_on, datetime(2017, 4, 19))
        self.assertEqual(episode_case.owner_id, '-')
        self.assertEqual(episode_case.dynamic_case_properties(), OrderedDict([
            ('adherence_schedule_date_start', '2017-04-19'),
            ('adherence_schedule_id', 'schedule_mwf'),
            ('date_of_diagnosis', '2017-04-18'),
            ('date_of_mo_signature', '2017-04-17'),
            ('disease_classification', 'extra_pulmonary'),
            ('dots_99_enabled', 'false'),
            ('episode_id', '20160908010203004'),
            ('episode_pending_registration', 'no'),
            ('episode_type', 'confirmed_tb'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
            ('nikshay_id', '02139-02215'),
            ('site_choice', 'abdominal'),
            ('transfer_in', ''),
            ('treatment_card_completed_date', '2017-04-20'),
            ('treatment_initiated', 'yes_private'),
            ('treatment_initiation_date', '2017-04-19'),
            ('weight', '50'),
        ]))
        self.assertEqual(len(episode_case.indices), 1)
        self._assertIndexEqual(
            episode_case.indices[0],
            CommCareCaseIndex(
                identifier='host',
                referenced_type='occurrence',
                referenced_id=occurrence_case.get_id,
                relationship='extension',
            )
        )
        self.assertEqual(len(episode_case.xform_ids), 1)

    def test_beneficiary_cured(self):
        Episode.objects.create(
            adherenceScore=0.5,
            alertFrequencyId=2,
            beneficiaryID=self.beneficiary,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            episodeDisplayID=3,
            episodeID=6,
            extraPulmonary='Abdomen',
            hiv='Negative',
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            newOrRetreatment='New',
            nikshayID='02139-02215',
            patientWeight=50,
            rxStartDate=datetime(2017, 4, 19),
            site='Extrapulmonary',
            treatmentOutcomeId='Cured',
            unknownAdherencePct=0.9,
            unresolvedMissedDosesPct=0.1,
        )
        call_command('create_cases_by_beneficiary', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertFalse(person_case.closed)
        self.assertEqual(person_case.owner_id, ARCHIVED_CASE_OWNER_ID)
        self.assertEqual(person_case.dynamic_case_properties()['is_active'], 'no')

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertTrue(occurrence_case.closed)

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertTrue(episode_case.closed)
        self.assertEqual(episode_case.dynamic_case_properties()['treatment_outcome'], 'cured')

    def test_beneficiary_died(self):
        Episode.objects.create(
            adherenceScore=0.5,
            alertFrequencyId=2,
            beneficiaryID=self.beneficiary,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            episodeDisplayID=3,
            episodeID=6,
            extraPulmonary='Abdomen',
            hiv='Negative',
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            newOrRetreatment='New',
            nikshayID='02139-02215',
            patientWeight=50,
            rxStartDate=datetime(2017, 4, 19),
            site='Extrapulmonary',
            treatmentOutcomeId='Died',
            unknownAdherencePct=0.9,
            unresolvedMissedDosesPct=0.1,
        )
        call_command('create_cases_by_beneficiary', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertTrue(person_case.closed)
        self.assertEqual(person_case.owner_id, ARCHIVED_CASE_OWNER_ID)
        self.assertEqual(person_case.dynamic_case_properties()['is_active'], 'no')

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertTrue(occurrence_case.closed)

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertTrue(episode_case.closed)
        self.assertEqual(episode_case.dynamic_case_properties()['treatment_outcome'], 'died')

    def test_adherence(self):
        episode = Episode.objects.create(
            adherenceScore=0.5,
            alertFrequencyId=2,
            beneficiaryID=self.beneficiary,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            episodeDisplayID=3,
            episodeID=1,
            extraPulmonary='Abdomen',
            hiv='Negative',
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            newOrRetreatment='New',
            nikshayID='02139-02215',
            patientWeight=50,
            rxStartDate=datetime(2017, 4, 19),
            site='Extrapulmonary',
            unknownAdherencePct=0.9,
            unresolvedMissedDosesPct=0.1,
        )
        Adherence.objects.create(
            adherenceId=5,
            dosageStatusId=0,
            doseDate=datetime(2017, 4, 22),
            doseReasonId=3,
            episodeId=episode,
            reportingMechanismId=4,
        )

        call_command('create_cases_by_beneficiary', self.domain)

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])

        adherence_case_ids = self.case_accessor.get_case_ids_in_domain(type='adherence')
        self.assertEqual(len(adherence_case_ids), 1)
        adherence_case = self.case_accessor.get_case(adherence_case_ids[0])
        self.assertFalse(adherence_case.closed)  # TODO
        self.assertIsNone(adherence_case.external_id)
        self.assertEqual(adherence_case.name, '2017-04-22')
        # self.assertEqual(adherence_case.opened_on, '')  # TODO
        self.assertEqual(adherence_case.owner_id, '-')
        self.assertEqual(adherence_case.dynamic_case_properties(), OrderedDict([
            ('adherence_date', '2017-04-22'),
            ('adherence_value', 'directly_observed_dose'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '5'),
        ]))
        self.assertEqual(len(adherence_case.indices), 1)
        self._assertIndexEqual(
            adherence_case.indices[0],
            CommCareCaseIndex(
                identifier='host',
                referenced_type='episode',
                referenced_id=episode_case.get_id,
                relationship='extension',
            )
        )
        self.assertEqual(len(adherence_case.xform_ids), 1)

    def test_multiple_adherences(self):
        episode = Episode.objects.create(
            id=1,
            adherenceScore=0.5,
            alertFrequencyId=2,
            beneficiaryID=self.beneficiary,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            episodeDisplayID=3,
            extraPulmonary='Abdomen',
            hiv='Negative',
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            newOrRetreatment='New',
            nikshayID='02139-02215',
            patientWeight=50,
            rxStartDate=datetime(2017, 4, 19),
            site='Extrapulmonary',
            unknownAdherencePct=0.9,
            unresolvedMissedDosesPct=0.1,
        )
        Adherence.objects.create(
            adherenceId=1,
            dosageStatusId=0,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode,
            reportingMechanismId=4,
        )
        Adherence.objects.create(
            adherenceId=2,
            dosageStatusId=1,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode,
            reportingMechanismId=4,
        )

        call_command('create_cases_by_beneficiary', self.domain)

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='episode')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='adherence')), 2)

    def test_prescription(self):
        EpisodePrescription.objects.create(
            id=1,
            beneficiaryId=self.beneficiary,
            numberOfDays=2,
            prescriptionID=3,
            pricePerUnit=0.5,
            productID=4,
            productName='drug name',
            refill_Index=5,
            voucherID=6,
        )

        call_command('create_cases_by_beneficiary', self.domain)

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])

        prescription_case_ids = self.case_accessor.get_case_ids_in_domain(type='prescription')
        self.assertEqual(len(prescription_case_ids), 1)
        prescription_case = self.case_accessor.get_case(prescription_case_ids[0])
        self.assertFalse(prescription_case.closed)  # TODO
        self.assertIsNone(prescription_case.external_id)
        self.assertEqual(prescription_case.name, 'drug name')
        # self.assertEqual(adherence_case.opened_on, '')  # TODO
        self.assertEqual(prescription_case.owner_id, '-')
        self.assertEqual(prescription_case.dynamic_case_properties(), OrderedDict([
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
        ]))
        self.assertEqual(len(prescription_case.indices), 1)
        self._assertIndexEqual(
            prescription_case.indices[0],
            CommCareCaseIndex(
                identifier='host',
                referenced_type='episode',
                referenced_id=episode_case.get_id,
                relationship='extension',
            )
        )
        self.assertEqual(len(prescription_case.xform_ids), 1)

    def test_multiple_prescriptions(self):
        EpisodePrescription.objects.create(
            id=1,
            beneficiaryId=self.beneficiary,
            numberOfDays=2,
            prescriptionID=3,
            pricePerUnit=0.5,
            productID=4,
            refill_Index=5,
            voucherID=6,
        )
        EpisodePrescription.objects.create(
            id=2,
            beneficiaryId=self.beneficiary,
            numberOfDays=2,
            prescriptionID=3,
            pricePerUnit=0.5,
            productID=4,
            refill_Index=5,
            voucherID=6,
        )

        call_command('create_cases_by_beneficiary', self.domain)

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='episode')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='prescription')), 2)

    def test_labtest(self):
        episode = Episode.objects.create(
            id=1,
            adherenceScore=0.5,
            alertFrequencyId=2,
            beneficiaryID=self.beneficiary,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            episodeDisplayID=3,
            hiv='Negative',
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            patientWeight=50,
            rxStartDate=datetime(2017, 4, 19),
            site='Extrapulmonary',
            unknownAdherencePct=0.9,
            unresolvedMissedDosesPct=0.1,
        )
        LabTest.objects.create(
            id=1,
            episodeId=episode,
            labId=2,
            tbStatusId=3,
            testId=4,
            testSiteId=5,
            testSiteSpecimenId=6,
            testSpecimenId=7,
            treatmentCardId=8,
            treatmentFileId=9,
            voucherNumber=10,
        )

        call_command('create_cases_by_beneficiary', self.domain)

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(len(occurrence_case_ids), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='episode')), 1)

        test_case_ids = self.case_accessor.get_case_ids_in_domain(type='test')
        self.assertEqual(len(test_case_ids), 1)
        test_case = self.case_accessor.get_case(test_case_ids[0])
        self.assertFalse(test_case.closed)  # TODO
        self.assertIsNone(test_case.external_id)
        self.assertEqual(test_case.name, None)  # TODO
        # self.assertEqual(adherence_case.opened_on, '')  # TODO
        self.assertEqual(test_case.owner_id, '-')
        self.assertEqual(test_case.dynamic_case_properties(), OrderedDict([
            ('migration_created_case', 'true'),
        ]))
        self.assertEqual(len(test_case.indices), 1)
        self._assertIndexEqual(
            test_case.indices[0],
            CommCareCaseIndex(
                identifier='host',
                referenced_type='occurrence',
                referenced_id=occurrence_case_ids[0],
                relationship='extension',
            )
        )
        self.assertEqual(len(test_case.xform_ids), 1)

    def test_multiple_labtests(self):
        episode = Episode.objects.create(
            id=1,
            adherenceScore=0.5,
            alertFrequencyId=2,
            beneficiaryID=self.beneficiary,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            episodeDisplayID=3,
            hiv='Negative',
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            patientWeight=50,
            rxStartDate=datetime(2017, 4, 19),
            site='Extrapulmonary',
            unknownAdherencePct=0.9,
            unresolvedMissedDosesPct=0.1,
        )
        LabTest.objects.create(
            id=1,
            episodeId=episode,
            labId=2,
            tbStatusId=3,
            testId=4,
            testSiteId=5,
            testSiteSpecimenId=6,
            testSpecimenId=7,
            treatmentCardId=8,
            treatmentFileId=9,
            voucherNumber=10,
        )
        LabTest.objects.create(
            id=2,
            episodeId=episode,
            labId=2,
            tbStatusId=3,
            testId=4,
            testSiteId=5,
            testSiteSpecimenId=6,
            testSpecimenId=7,
            treatmentCardId=8,
            treatmentFileId=9,
            voucherNumber=10,
        )

        call_command('create_cases_by_beneficiary', self.domain)

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='episode')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='test')), 2)

    def _assertIndexEqual(self, index_1, index_2):
        self.assertEqual(index_1.identifier, index_2.identifier)
        self.assertEqual(index_1.referenced_type, index_2.referenced_type)
        self.assertEqual(index_1.referenced_id, index_2.referenced_id)
        self.assertEqual(index_1.relationship, index_2.relationship)
