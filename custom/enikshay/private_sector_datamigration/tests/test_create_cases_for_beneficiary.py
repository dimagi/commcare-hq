from __future__ import absolute_import
from collections import OrderedDict
from datetime import date, datetime

from django.core.management import call_command
from django.test import TestCase, override_settings

from mock import Mock, patch

from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID
from casexml.apps.case.sharedmodels import CommCareCaseIndex

from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.locations.tasks import make_location_user
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.private_sector_datamigration.models import (
    Adherence,
    Agency,
    Beneficiary,
    EpisodePrescription,
    Episode,
    UserDetail,
    Voucher,
)
from custom.enikshay.tests.utils import ENikshayLocationStructureMixin
from custom.enikshay.user_setup import set_issuer_id


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
            blockOrHealthPostId='101',
            caseId='3',
            caseStatus='patient',
            configureAlert='Yes',
            creationDate=datetime(2017, 1, 1),
            creator='creator',
            dateOfRegn=datetime(2017, 4, 17),
            districtId='102',
            dob=datetime(1992, 1, 2),
            emergencyContactNo='1234567890',
            fatherHusbandName='Nick Sr.',
            firstName='Nick',
            gender='4',
            identificationNumber='98765',
            identificationTypeId='16',
            isActive=True,
            languagePreferences='132',
            lastName='P',
            organisationId=2,
            phoneNumber='5432109876',
            pincode=822113,
            referredQP='org123',
            subOrganizationId=3,
            stateId='103',
            villageTownCity='Cambridge',
            wardId='104',
        )
        cls.case_accessor = CaseAccessors(cls.domain)

        cls.agency = Agency.objects.create(
            agencyId=1,
            agencyTypeId='ATPR',
            agencySubTypeId='PRQP',
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

    @patch('custom.enikshay.user_setup.IssuerId.pk')
    def setUp(self, mock_pk):
        mock_pk.__get__ = Mock(return_value=7)
        super(TestCreateCasesByBeneficiary, self).setUp()

        self.pcp.site_code = str(self.agency.agencyId)
        self.pcp.save()

        self.virtual_location_user = make_location_user(self.pcp)
        set_issuer_id(self.domain, self.virtual_location_user)
        self.virtual_location_user.save()

        self.pcp.user_id = self.virtual_location_user._id
        self.pcp.save()

        self.default_location = SQLLocation.objects.create(
            domain=self.domain,
            location_type=self.pcp.location_type,
            site_code='default',
        )

        self.default_location_user = make_location_user(self.default_location)
        set_issuer_id(self.domain, self.default_location_user)
        self.default_location_user.save()

        self.default_location.user_id = self.default_location_user._id
        self.default_location.save()

    def tearDown(self):
        self.virtual_location_user.delete()
        self.default_location_user.delete()
        super(TestCreateCasesByBeneficiary, self).tearDown()

    @patch('custom.enikshay.private_sector_datamigration.factory.datetime')
    @patch('custom.enikshay.private_sector_datamigration.factory.MigratedBeneficiaryCounter')
    def test_create_cases_for_beneficiary(self, mock_counter, mock_datetime):
        mock_counter.get_next_counter.return_value = 4
        mock_datetime.utcnow.return_value = datetime(2016, 9, 8, 1, 2, 3, 4123)

        creating_loc = SQLLocation.active_objects.create(
            domain=self.domain,
            location_type=LocationType.objects.get(code='pcp'),
            name='creating location',
            site_code='2',
            user_id='dummy_user_id',
        )

        creating_agency = Agency.objects.create(
            agencyId=2,
            agencyTypeId='ATPR',
            agencySubTypeId='PRQP',
            creationDate=datetime(2017, 5, 1),
            dateOfRegn=datetime(2017, 5, 1),
            modificationDate=datetime(2017, 5, 1),
            nikshayId='123457',
            organisationId=2,
            parentAgencyId=3,
            subOrganisationId=4,
        )
        UserDetail.objects.create(
            id=1,
            agencyId=creating_agency.agencyId,
            isPrimary=True,
            motechUserName='creator',
            organisationId=2,
            passwordResetFlag=False,
            pincode=3,
            subOrganisationId=4,
            userId=5,
            valid=True,
        )

        Episode.objects.create(
            adherenceScore=0.5,
            alertFrequencyId=2,
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            diabetes='Yes',
            dstStatus='Rifampicin sensitive',
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
            rxOutcomeDate=datetime(2017, 5, 19),
            site='Extrapulmonary',
            treatmentPhase='Continuation Phase',
            unknownAdherencePct=0.9,
            unresolvedMissedDosesPct=0.1,
        )
        call_command('create_cases_by_beneficiary', self.domain, 'tests')

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
            ('contact_phone_number', '915432109876'),
            ('created_by_user_type', 'pcp'),
            ('current_address', '585 Mass Ave, Suite 4'),
            ('current_address_postal_code', '822113'),
            ('current_address_village_town_city', 'Cambridge'),
            ('current_episode_type', 'confirmed_tb'),
            ('dataset', 'real'),
            ('diabetes_status', 'diabetic'),
            ('dob', '1992-01-02'),
            ('dob_entered', '1992-01-02'),
            ('dob_known', 'yes'),
            ('enrolled_in_private', 'true'),
            ('facility_assigned_to', self.pcp.location_id),
            ('first_name', 'Nick'),
            ('hiv_status', 'non_reactive'),
            ('husband_father_name', 'Nick Sr.'),
            ('id_original_beneficiary_count', '4'),
            ('id_original_device_number', '0'),
            ('id_original_issuer_number', '7'),
            ('is_active', 'yes'),
            ('language_code', 'hin'),
            ('last_name', 'P'),
            ('legacy_blockOrHealthPostId', '101'),
            ('legacy_districtId', '102'),
            ('legacy_organisationId', '2'),
            ('legacy_stateId', '103'),
            ('legacy_subOrganizationId', '3'),
            ('legacy_wardId', '104'),
            ('migration_comment', 'tests'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
            ('person_id', 'AAA-KAA-AF'),
            ('person_id_flat', 'AAAKAAAF'),
            ('person_id_legacy', '3'),
            ('person_occurrence_count', '1'),
            ('phone_number', '5432109876'),
            ('registered_by', creating_loc.location_id),
            ('search_name', 'Nick P'),
            ('secondary_phone', '1234567890'),
            ('send_alerts', 'yes'),
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
            ('legacy_blockOrHealthPostId', '101'),
            ('legacy_districtId', '102'),
            ('legacy_organisationId', '2'),
            ('legacy_stateId', '103'),
            ('legacy_subOrganizationId', '3'),
            ('legacy_wardId', '104'),
            ('migration_comment', 'tests'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
            ('occurrence_episode_count', '1'),
            ('occurrence_id', '20160908010203004'),
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
            ('adherence_total_doses_taken', '0'),
            ('adherence_tracking_mechanism', ''),
            ('basis_of_diagnosis', 'clinical_other'),
            ('case_definition', 'clinical'),
            ('created_by_user_type', 'pcp'),
            ('date_of_diagnosis', '2017-04-18'),
            ('date_of_mo_signature', '2017-04-17'),
            ('diagnosing_facility_id', self.pcp.location_id),
            ('disease_classification', 'extrapulmonary'),
            ('dots_99_enabled', 'false'),
            ('dst_status', 'rif_sensitive'),
            ('enrolled_in_private', 'true'),
            ('episode_details_complete', 'true'),
            ('episode_id', '20160908010203004'),
            ('episode_pending_registration', 'no'),
            ('episode_type', 'confirmed_tb'),
            ('legacy_blockOrHealthPostId', '101'),
            ('legacy_districtId', '102'),
            ('legacy_organisationId', '2'),
            ('legacy_stateId', '103'),
            ('legacy_subOrganizationId', '3'),
            ('legacy_wardId', '104'),
            ('migration_comment', 'tests'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
            ('new_retreatment', 'new'),
            ('nikshay_id', '02139-02215'),
            ('patient_type', 'new'),
            ('private_sector_episode_pending_registration', 'no'),
            ('registered_by', creating_loc.location_id),
            ('retreatment_reason', ''),
            ('site', 'extrapulmonary'),
            ('site_choice', 'abdominal'),
            ('transfer_in', ''),
            ('treatment_card_completed_date', '2017-04-20'),
            ('treatment_initiated', 'yes_pcp'),
            ('treatment_initiation_date', '2017-04-19'),
            ('treatment_options', ''),
            ('treatment_outcome_date', '2017-05-19'),
            ('treatment_phase', 'continuation_phase_cp'),
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
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            dstStatus='Rifampicin sensitive',
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
        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertFalse(person_case.closed)
        self.assertEqual(person_case.owner_id, ARCHIVED_CASE_OWNER_ID)
        self.assertEqual(person_case.dynamic_case_properties()['archive_reason'], 'cured')
        self.assertEqual(person_case.dynamic_case_properties()['is_active'], 'no')
        self.assertEqual(person_case.dynamic_case_properties()['last_owner'], self.pcp.location_id)
        self.assertTrue('last_reason_to_close' not in person_case.dynamic_case_properties())

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
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            dstStatus='Rifampicin sensitive',
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
        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertTrue(person_case.closed)
        self.assertEqual(person_case.owner_id, ARCHIVED_CASE_OWNER_ID)
        self.assertEqual(person_case.dynamic_case_properties()['archive_reason'], 'died')
        self.assertEqual(person_case.dynamic_case_properties()['is_active'], 'no')
        self.assertEqual(person_case.dynamic_case_properties()['last_owner'], self.pcp.location_id)
        self.assertEqual(person_case.dynamic_case_properties()['last_reason_to_close'], 'died')

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertTrue(occurrence_case.closed)

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertTrue(episode_case.closed)
        self.assertEqual(episode_case.dynamic_case_properties()['treatment_outcome'], 'died')

    def test_id_original_beneficiary_count(self):
        call_command('create_cases_by_beneficiary', self.domain, 'tests')
        call_command('create_cases_by_beneficiary', self.domain, 'tests')
        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 2)
        self.assertEqual(
            abs(int(self.case_accessor.get_case(
                person_case_ids[0]).dynamic_case_properties()['id_original_beneficiary_count'])
            - int(self.case_accessor.get_case(
                person_case_ids[1]).dynamic_case_properties()['id_original_beneficiary_count'])),
            1
        )

    def test_default_location_owner(self):
        self.agency.agencyTypeId = 'ATFO'
        self.agency.save()

        call_command(
            'create_cases_by_beneficiary', self.domain, 'tests',
            default_location_owner_id=self.default_location.location_id,
        )

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(person_case.owner_id, self.default_location.location_id)

    def test_default_location_owner_not_used(self):

        call_command(
            'create_cases_by_beneficiary', self.domain, 'tests',
            default_location_owner_id=self.default_location.location_id,
        )

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(person_case.owner_id, self.pcp.location_id)

    @patch('custom.enikshay.private_sector_datamigration.factory.date')
    def test_closed_adherence(self, mock_today):
        mock_today.today.return_value = date(2017, 6, 1)

        episode = Episode.objects.create(
            adherenceScore=0.5,
            alertFrequencyId=2,
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            dstStatus='Rifampicin sensitive',
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
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=0,
            doseDate=datetime(2017, 4, 22),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=86,
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(episode_case.dynamic_case_properties()['adherence_total_doses_taken'], '1')

        adherence_case_ids = self.case_accessor.get_case_ids_in_domain(type='adherence')
        self.assertEqual(len(adherence_case_ids), 1)
        adherence_case = self.case_accessor.get_case(adherence_case_ids[0])
        self.assertTrue(adherence_case.closed)
        self.assertIsNone(adherence_case.external_id)
        self.assertEqual(adherence_case.name, '2017-04-22')
        self.assertEqual(adherence_case.opened_on, datetime(2017, 4, 21))
        self.assertEqual(adherence_case.owner_id, '-')
        self.assertEqual(adherence_case.dynamic_case_properties(), OrderedDict([
            ('adherence_closure_reason', 'historical'),
            ('adherence_date', '2017-04-22'),
            ('adherence_report_source', 'treatment_supervisor'),
            ('adherence_source', 'enikshay'),
            ('adherence_value', 'directly_observed_dose'),
            ('migration_comment', 'tests'),
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

    @patch('custom.enikshay.private_sector_datamigration.factory.date')
    def test_open_adherence(self, mock_today):
        mock_today.today.return_value = date(2017, 4, 23)

        episode = Episode.objects.create(
            adherenceScore=0.5,
            alertFrequencyId=2,
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            dstStatus='Rifampicin sensitive',
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
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=0,
            doseDate=datetime(2017, 4, 22),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=86,
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        adherence_case_ids = self.case_accessor.get_case_ids_in_domain(type='adherence')
        self.assertEqual(len(adherence_case_ids), 1)
        adherence_case = self.case_accessor.get_case(adherence_case_ids[0])
        self.assertFalse(adherence_case.closed)
        self.assertEqual(adherence_case.opened_on, datetime(2017, 4, 21))
        self.assertEqual(adherence_case.dynamic_case_properties()['adherence_date'], '2017-04-22')
        self.assertNotIn('adherence_closure_reason', adherence_case.dynamic_case_properties())

    def test_multiple_adherences(self):
        episode = Episode.objects.create(
            id=1,
            adherenceScore=0.5,
            alertFrequencyId=2,
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            dstStatus='Rifampicin sensitive',
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
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=0,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=85,
        )
        Adherence.objects.create(
            adherenceId=2,
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=1,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=96,
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(episode_case.dynamic_case_properties()['adherence_total_doses_taken'], '1')

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='adherence')), 2)

    def test_skip_adherence(self):
        episode = Episode.objects.create(
            id=1,
            adherenceScore=0.5,
            alertFrequencyId=2,
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            dstStatus='Rifampicin sensitive',
            episodeDisplayID=3,
            episodeID='123',
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
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=0,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=85,
        )
        Adherence.objects.create(
            adherenceId=2,
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=1,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=96,
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests', skip_adherence=True)

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(episode_case.dynamic_case_properties()['adherence_total_doses_taken'], '1')

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='adherence')), 0)

    def test_dots_99_enabled_false(self):
        episode = Episode.objects.create(
            id=1,
            adherenceScore=0.5,
            alertFrequencyId=2,
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            dstStatus='Rifampicin sensitive',
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
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=0,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=85,
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(episode_case.dynamic_case_properties()['adherence_tracking_mechanism'], 'field_officer')
        self.assertEqual(episode_case.dynamic_case_properties()['dots_99_enabled'], 'false')

    def test_dots_99_enabled_true(self):
        episode = Episode.objects.create(
            id=1,
            adherenceScore=0.5,
            alertFrequencyId=2,
            basisOfDiagnosis='Clinical - Other',
            beneficiaryID=self.beneficiary.caseId,
            creationDate=datetime(2017, 4, 20),
            dateOfDiagnosis=datetime(2017, 4, 18),
            dstStatus='Rifampicin sensitive',
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
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=0,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=84,
        )
        Adherence.objects.create(
            adherenceId=2,
            creationDate=datetime(2017, 4, 21),
            dosageStatusId=1,
            doseDate=datetime.utcnow(),
            doseReasonId=3,
            episodeId=episode.episodeID,
            reportingMechanismId=0,
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(episode_case.dynamic_case_properties()['adherence_tracking_mechanism'], '99dots')
        self.assertEqual(episode_case.dynamic_case_properties()['dots_99_enabled'], 'true')

    def test_prescription(self):
        EpisodePrescription.objects.create(
            id=1,
            beneficiaryId=self.beneficiary.caseId,
            creationDate=datetime(2017, 5, 26),
            numberOfDays=2,
            numberOfDaysPrescribed='2',
            prescriptionID=3,
            pricePerUnit=0.5,
            productID=4,
            productName='drug name',
            refill_Index=5,
            voucherID=6,
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])

        prescription_case_ids = self.case_accessor.get_case_ids_in_domain(type='prescription')
        self.assertEqual(len(prescription_case_ids), 1)
        prescription_case = self.case_accessor.get_case(prescription_case_ids[0])
        self.assertTrue(prescription_case.closed)
        self.assertIsNone(prescription_case.external_id)
        self.assertEqual(prescription_case.name, 'drug name')
        self.assertEqual(prescription_case.owner_id, '-')
        self.assertEqual(prescription_case.dynamic_case_properties(), OrderedDict([
            ('date_ordered', '2017-05-26'),
            ('migration_comment', 'tests'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
            ('number_of_days_prescribed', '2'),
        ]))
        self.assertEqual(len(prescription_case.indices), 1)
        self._assertIndexEqual(
            prescription_case.indices[0],
            CommCareCaseIndex(
                identifier='episode_of_prescription',
                referenced_type='episode',
                referenced_id=episode_case.get_id,
                relationship='extension',
            )
        )
        self.assertEqual(len(prescription_case.xform_ids), 1)

    def test_prescription_with_date_fulfilled(self):
        EpisodePrescription.objects.create(
            id=1,
            beneficiaryId=self.beneficiary.caseId,
            creationDate=datetime(2017, 5, 26),
            numberOfDays=2,
            numberOfDaysPrescribed='2',
            prescriptionID=3,
            pricePerUnit=0.5,
            productID=4,
            productName='drug name',
            refill_Index=5,
            voucherID=6,
        )
        Voucher.objects.create(
            id=2,
            creationDate=datetime(2017, 5, 31),
            modificationDate=datetime(2017, 5, 31),
            voucherCreatedDate=datetime(2017, 5, 31),
            voucherNumber=6,
            voucherStatusId='3',
            voucherUsedDate=datetime(2017, 6, 1),
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(len(episode_case_ids), 1)
        episode_case = self.case_accessor.get_case(episode_case_ids[0])

        prescription_case_ids = self.case_accessor.get_case_ids_in_domain(type='prescription')
        self.assertEqual(len(prescription_case_ids), 1)
        prescription_case = self.case_accessor.get_case(prescription_case_ids[0])
        self.assertTrue(prescription_case.closed)
        self.assertIsNone(prescription_case.external_id)
        self.assertEqual(prescription_case.name, 'drug name')
        self.assertEqual(prescription_case.owner_id, '-')
        self.assertEqual(prescription_case.dynamic_case_properties(), OrderedDict([
            ('date_fulfilled', '2017-06-01'),
            ('date_ordered', '2017-05-26'),
            ('migration_comment', 'tests'),
            ('migration_created_case', 'true'),
            ('migration_created_from_record', '3'),
            ('number_of_days_prescribed', '2'),
        ]))
        self.assertEqual(len(prescription_case.indices), 1)
        self._assertIndexEqual(
            prescription_case.indices[0],
            CommCareCaseIndex(
                identifier='episode_of_prescription',
                referenced_type='episode',
                referenced_id=episode_case.get_id,
                relationship='extension',
            )
        )
        self.assertEqual(len(prescription_case.xform_ids), 1)

    def test_multiple_prescriptions(self):
        EpisodePrescription.objects.create(
            id=1,
            beneficiaryId=self.beneficiary.caseId,
            creationDate=datetime(2017, 5, 26),
            numberOfDays=2,
            prescriptionID=3,
            pricePerUnit=0.5,
            productID=4,
            refill_Index=5,
            voucherID=6,
        )
        EpisodePrescription.objects.create(
            id=2,
            beneficiaryId=self.beneficiary.caseId,
            creationDate=datetime(2017, 5, 26),
            numberOfDays=2,
            prescriptionID=3,
            pricePerUnit=0.5,
            productID=4,
            refill_Index=5,
            voucherID=6,
        )

        call_command('create_cases_by_beneficiary', self.domain, 'tests')

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='person')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='episode')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='prescription')), 2)


    def test_set_location_owner(self):
        Agency.objects.all().delete()
        UserDetail.objects.all().delete()

        call_command('create_cases_by_beneficiary', self.domain, 'tests', location_owner_id=self.pcp.location_id)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(len(person_case_ids), 1)
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(person_case.owner_id, self.pcp.location_id)

        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='occurrence')), 1)
        self.assertEqual(len(self.case_accessor.get_case_ids_in_domain(type='episode')), 1)

    def _assertIndexEqual(self, index_1, index_2):
        self.assertEqual(index_1.identifier, index_2.identifier)
        self.assertEqual(index_1.referenced_type, index_2.referenced_type)
        self.assertEqual(index_1.referenced_id, index_2.referenced_id)
        self.assertEqual(index_1.relationship, index_2.relationship)
