from collections import OrderedDict
from datetime import datetime

from django.core.management import call_command
from django.test import TestCase, override_settings

from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.private_sector_datamigration.models import (
    Adherence,
    Beneficiary,
    EpisodePrescription,
    LabTest,
    Episode)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestCreateCasesByBeneficiary(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestCreateCasesByBeneficiary, cls).setUpClass()
        cls.beneficiary = Beneficiary.objects.create(
            id=1,
            isActive=True,
            organisationId=2,
        )
        cls.domain = 'test_domain'
        cls.case_accessor = CaseAccessors(cls.domain)

    def test_create_cases_for_beneficiary(self):
        call_command('create_cases_by_beneficiary', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertFalse(person_case.closed)  # TODO - update by outcome
        self.assertIsNone(person_case.external_id)
        self.assertEqual(person_case.name, None)  # TODO  - assign
        # self.assertEqual(person_case.opened_on, '')  # TODO
        self.assertEqual(person_case.owner_id, '')  # TODO - assign to location
        self.assertEqual(person_case.dynamic_case_properties(), OrderedDict([]))
        self.assertEqual(len(person_case.xform_ids), 1)

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(len(occurrence_case_ids), 1)
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertFalse(occurrence_case.closed)  # TODO - update by outcome
        self.assertIsNone(occurrence_case.external_id)
        self.assertEqual(occurrence_case.name, 'Occurrence #1')
        # self.assertEqual(occurrence_case.opened_on, '')  # TODO
        self.assertEqual(occurrence_case.owner_id, '')
        self.assertEqual(occurrence_case.dynamic_case_properties(), OrderedDict([]))
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
        self.assertFalse(episode_case.closed)  # TODO - update by outcome
        self.assertIsNone(episode_case.external_id)  # TODO - update with nikshay ID
        self.assertEqual(episode_case.name, 'Episode #1: Confirmed TB (Patient)')
        # self.assertEqual(episode_case.opened_on, '')  # TODO
        self.assertEqual(episode_case.owner_id, '')
        self.assertEqual(episode_case.dynamic_case_properties(), OrderedDict([]))
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

    def test_adherence(self):
        Adherence.objects.create(
            id=1,
            beneficiaryId=self.beneficiary,
            dosageStatusId=2,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
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
        self.assertIsNone(adherence_case.external_id)  # TODO - update with nikshay ID
        self.assertEqual(adherence_case.name, None)  # TODO
        # self.assertEqual(adherence_case.opened_on, '')  # TODO
        self.assertEqual(adherence_case.owner_id, '')
        self.assertEqual(adherence_case.dynamic_case_properties(), OrderedDict([]))
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
        Adherence.objects.create(
            id=1,
            beneficiaryId=self.beneficiary,
            dosageStatusId=2,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            reportingMechanismId=4,
        )
        Adherence.objects.create(
            id=2,
            beneficiaryId=self.beneficiary,
            dosageStatusId=2,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
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
        self.assertIsNone(prescription_case.external_id)  # TODO - update with nikshay ID
        self.assertEqual(prescription_case.name, None)  # TODO
        # self.assertEqual(adherence_case.opened_on, '')  # TODO
        self.assertEqual(prescription_case.owner_id, '')
        self.assertEqual(prescription_case.dynamic_case_properties(), OrderedDict([]))
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
            episodeDisplayID=3,
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            patientWeight=50,
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
        self.assertIsNone(test_case.external_id)  # TODO - update with nikshay ID
        self.assertEqual(test_case.name, None)  # TODO
        # self.assertEqual(adherence_case.opened_on, '')  # TODO
        self.assertEqual(test_case.owner_id, '')
        self.assertEqual(test_case.dynamic_case_properties(), OrderedDict([]))
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
            episodeDisplayID=3,
            lastMonthAdherencePct=0.6,
            lastTwoWeeksAdherencePct=0.7,
            missedDosesPct=0.8,
            patientWeight=50,
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
