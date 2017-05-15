from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID, CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from custom.enikshay.private_sector_datamigration.models import (
    Adherence,
    Episode,
    EpisodePrescription,
    LabTest,
    MigratedBeneficiaryCounter,
    Voucher,
)
from custom.enikshay.user_setup import compress_nikshay_id

from dimagi.utils.decorators.memoized import memoized

PERSON_CASE_TYPE = 'person'
OCCURRENCE_CASE_TYPE = 'occurrence'
EPISODE_CASE_TYPE = 'episode'
ADHERENCE_CASE_TYPE = 'adherence'
PRESCRIPTION_CASE_TYPE = 'prescription'
TEST_CASE_TYPE = 'test'


def get_human_friendly_id():
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]


class BeneficiaryCaseFactory(object):

    def __init__(self, domain, beneficiary, location_owner):
        self.domain = domain
        self.beneficiary = beneficiary
        self.location_owner = location_owner

    def get_case_structures_to_create(self, skip_adherence):
        person_structure = self.get_person_case_structure()
        ocurrence_structure = self.get_occurrence_case_structure(person_structure)
        episode_structure = self.get_episode_case_structure(ocurrence_structure)
        episode_descendants = [
            self.get_prescription_case_structure(prescription, episode_structure)
            for prescription in self._prescriptions
        ]
        if not skip_adherence:
            episode_descendants.extend(
                self.get_adherence_case_structure(adherence, episode_structure)
                for adherence in self._adherences
            )
        episode_or_descendants = episode_descendants or [episode_structure]

        tests = [
            self.get_test_case_structure(labtest, ocurrence_structure)
            for labtest in self._labtests
        ]

        return episode_or_descendants + tests

    def get_person_case_structure(self):
        kwargs = {
            'attrs': {
                'case_type': PERSON_CASE_TYPE,
                'create': True,
                'update': {
                    'current_address': self.beneficiary.current_address,
                    'current_address_district_choice': self.beneficiary.current_address_district_choice(),
                    'current_address_state_choice': self.beneficiary.current_address_state_choice(),
                    'current_episode_type': self.beneficiary.current_episode_type,
                    'dataset': 'real',
                    'enrolled_in_private': 'true',
                    'first_name': self.beneficiary.firstName,
                    'husband_father_name': self.beneficiary.husband_father_name,
                    'id_original_beneficiary_count': self._serial_count,
                    'id_original_device_number': 0,
                    'id_original_issuer_number': self._id_issuer_number,
                    'language_preference': self.beneficiary.language_preference,
                    'last_name': self.beneficiary.lastName,
                    'name': self.beneficiary.name,
                    'person_id': self.person_id,
                    'person_id_flat': self.person_id_flat,
                    'person_id_legacy': self.beneficiary.caseId,
                    'person_occurrence_count': 1,
                    'phone_number': self.beneficiary.phoneNumber,
                    'search_name': self.beneficiary.name,
                    'send_alerts': self.beneficiary.send_alerts,
                    'secondary_phone': self.beneficiary.emergencyContactNo,

                    'migration_created_case': 'true',
                    'migration_created_from_record': self.beneficiary.caseId,
                }
            }
        }

        if self.beneficiary.age_entered is not None:
            kwargs['attrs']['update']['age'] = self.beneficiary.age_entered
            kwargs['attrs']['update']['age_entered'] = self.beneficiary.age_entered
        else:
            if self.beneficiary.dob is not None:
                kwargs['attrs']['update']['age'] = relativedelta(
                    self.beneficiary.creationDate, self.beneficiary.dob
                ).years
            else:
                kwargs['attrs']['update']['age'] = ''
            kwargs['attrs']['update']['age_entered'] = ''

        if self.beneficiary.dob is not None:
            kwargs['attrs']['update']['dob'] = self.beneficiary.dob.date()
            kwargs['attrs']['update']['dob_entered'] = self.beneficiary.dob.date()
            kwargs['attrs']['update']['dob_known'] = 'yes'
        else:
            if self.beneficiary.age_entered is not None:
                kwargs['attrs']['update']['dob'] = date(date.today().year - self.beneficiary.age_entered, 7, 1),
            else:
                kwargs['attrs']['update']['dob'] = ''
            kwargs['attrs']['update']['dob_known'] = 'no'

        if self.beneficiary.sex is not None:
            kwargs['attrs']['update']['sex'] = self.beneficiary.sex

        if self.beneficiary.has_aadhaar_number:
            kwargs['attrs']['update']['aadhaar_number'] = self.beneficiary.identificationNumber
        else:
            kwargs['attrs']['update']['other_id_type'] = self.beneficiary.other_id_type
            if self.beneficiary.other_id_type != 'none':
                kwargs['attrs']['update']['other_id_number'] = self.beneficiary.identificationNumber

        kwargs['attrs']['update']['facility_assigned_to'] = self._location_owner_id

        if self._episode:
            kwargs['attrs']['update']['diabetes_status'] = self._episode.diabetes_status
            kwargs['attrs']['update']['hiv_status'] = self._episode.hiv_status

            if self._episode.is_treatment_ended:
                kwargs['attrs']['owner_id'] = ARCHIVED_CASE_OWNER_ID
                kwargs['attrs']['update']['archive_reason'] = self._episode.treatment_outcome
                kwargs['attrs']['update']['is_active'] = 'no'
                kwargs['attrs']['update']['last_owner'] = self._location_owner_id
                if self._episode.treatment_outcome == 'died':
                    kwargs['attrs']['close'] = True
                    kwargs['attrs']['update']['last_reason_to_close'] = self._episode.treatment_outcome
            else:
                kwargs['attrs']['owner_id'] = self._location_owner_id
                kwargs['attrs']['update']['is_active'] = 'yes'
        else:
            kwargs['attrs']['owner_id'] = self._location_owner_id

        return CaseStructure(**kwargs)

    def get_occurrence_case_structure(self, person_structure):
        kwargs = {
            'attrs': {
                'case_type': OCCURRENCE_CASE_TYPE,
                'create': True,
                'owner_id': '-',
                'update': {
                    'current_episode_type': self.beneficiary.current_episode_type,
                    'name': 'Occurrence #1',
                    'occurrence_episode_count': 1,
                    'occurrence_id': get_human_friendly_id(),

                    'migration_created_case': 'true',
                    'migration_created_from_record': self.beneficiary.caseId,
                }
            },
            'indices': [CaseIndex(
                person_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=PERSON_CASE_TYPE,
            )],
        }

        if self._episode and self._episode.is_treatment_ended:
            kwargs['attrs']['close'] = True

        return CaseStructure(**kwargs)

    def get_episode_case_structure(self, occurrence_structure):
        kwargs = {
            'attrs': {
                'case_type': EPISODE_CASE_TYPE,
                'create': True,
                'owner_id': '-',
                'update': {
                    'date_of_mo_signature': self.beneficiary.dateOfRegn.date(),
                    'diagnosing_facility_id': self._location_owner_id,
                    'enrolled_in_private': 'true',
                    'episode_id': get_human_friendly_id(),
                    'episode_type': self.beneficiary.current_episode_type,
                    'name': self.beneficiary.episode_name,
                    'transfer_in': '',
                    'treatment_options': '',

                    'migration_created_case': 'true',
                    'migration_created_from_record': self.beneficiary.caseId,
                }
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }

        if self._episode:
            rx_start_datetime = self._episode.rxStartDate
            kwargs['attrs']['date_opened'] = rx_start_datetime
            kwargs['attrs']['update']['adherence_total_doses_taken'] = self._episode.adherence_total_doses_taken
            kwargs['attrs']['update']['adherence_tracking_mechanism'] = self._episode.adherence_tracking_mechanism
            kwargs['attrs']['update']['basis_of_diagnosis'] = self._episode.basis_of_diagnosis
            kwargs['attrs']['update']['case_definition'] = self._episode.case_definition
            kwargs['attrs']['update']['date_of_diagnosis'] = self._episode.dateOfDiagnosis.date()
            kwargs['attrs']['update']['disease_classification'] = self._episode.disease_classification
            kwargs['attrs']['update']['dots_99_enabled'] = self._episode.dots_99_enabled
            kwargs['attrs']['update']['dst_status'] = self._episode.dst_status
            kwargs['attrs']['update']['episode_details_complete'] = 'true'
            kwargs['attrs']['update']['episode_pending_registration'] = (
                'yes' if self._episode.nikshayID is None else 'no'
            )
            kwargs['attrs']['update']['new_retreatment'] = self._episode.new_retreatment
            kwargs['attrs']['update']['patient_type'] = self._episode.patient_type
            kwargs['attrs']['update']['private_sector_episode_pending_registration'] = (
                'yes' if self._episode.nikshayID is None else 'no'
            )
            kwargs['attrs']['update']['retreatment_reason'] = self._episode.retreatment_reason
            kwargs['attrs']['update']['site'] = self._episode.site_property
            kwargs['attrs']['update']['site_choice'] = self._episode.site_choice
            kwargs['attrs']['update']['treatment_card_completed_date'] = self._episode.creationDate.date()
            kwargs['attrs']['update']['treatment_initiated'] = 'yes_pcp'
            kwargs['attrs']['update']['treatment_initiation_date'] = rx_start_datetime.date()
            kwargs['attrs']['update']['treatment_phase'] = self._episode.treatment_phase
            kwargs['attrs']['update']['weight'] = int(self._episode.patientWeight)

            if self._episode.nikshayID:
                kwargs['attrs']['external_id'] = self._episode.nikshayID
                kwargs['attrs']['update']['nikshay_id'] = self._episode.nikshayID

            if self._episode.rxOutcomeDate is not None:
                kwargs['attrs']['update']['rx_outcome_date'] = self._episode.rxOutcomeDate.date()

            if self._episode.disease_classification == 'extra_pulmonary':
                kwargs['attrs']['update']['site_choice'] = self._episode.site_choice

            if self._episode.treatment_outcome:
                kwargs['attrs']['update']['treatment_outcome'] = self._episode.treatment_outcome

            if self._episode.is_treatment_ended:
                kwargs['attrs']['close'] = True
        else:
            kwargs['attrs']['update']['adherence_total_doses_taken'] = 0
            kwargs['attrs']['update']['adherence_tracking_mechanism'] = ''
            kwargs['attrs']['update']['dots_99_enabled'] = 'false'
            kwargs['attrs']['update']['episode_pending_registration'] = 'yes'
            kwargs['attrs']['update']['private_sector_episode_pending_registration'] = 'yes'
            kwargs['attrs']['update']['treatment_initiated'] = 'no'

        return CaseStructure(**kwargs)

    def get_adherence_case_structure(self, adherence, episode_structure):
        kwargs = {
            'attrs': {
                'case_type': ADHERENCE_CASE_TYPE,
                'close': False,
                'create': True,
                'date_opened': adherence.creationDate,
                'owner_id': '-',
                'update': {
                    'adherence_date': adherence.doseDate.date(),
                    'adherence_value': adherence.adherence_value,
                    'name': adherence.doseDate.date(),

                    'migration_created_case': 'true',
                    'migration_created_from_record': adherence.adherenceId,
                }
            },
            'indices': [CaseIndex(
                episode_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=EPISODE_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    def get_prescription_case_structure(self, prescription, episode_structure):
        kwargs = {
            'attrs': {
                'case_type': PRESCRIPTION_CASE_TYPE,
                'close': True,
                'create': True,
                'owner_id': '-',
                'update': {
                    'date_ordered': prescription.creationDate.date(),
                    'name': prescription.productName,
                    'number_of_days_prescribed': prescription.numberOfDaysPrescribed,

                    'migration_created_case': 'true',
                    'migration_created_from_record': prescription.prescriptionID,
                }
            },
            'indices': [CaseIndex(
                episode_structure,
                identifier='episode_of_prescription',
                relationship=CASE_INDEX_EXTENSION,
                related_type=EPISODE_CASE_TYPE,
            )],
        }

        try:
            voucher = Voucher.objects.get(voucherNumber=prescription.voucherID)
            if voucher.voucherStatusId == '3':
                kwargs['attrs']['update']['date_fulfilled'] = voucher.voucherUsedDate.date()
        except Voucher.DoesNotExist:
            pass

        return CaseStructure(**kwargs)

    def get_test_case_structure(self, labtest, occurrence_structure):
        kwargs = {
            'attrs': {
                'case_type': TEST_CASE_TYPE,
                'close': False,
                'create': True,
                'owner_id': '-',
                'update': {
                    'migration_created_case': 'true',
                }
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }
        return CaseStructure(**kwargs)

    @property
    @memoized
    def _episode(self):
        episodes = Episode.objects.filter(beneficiaryID=self.beneficiary.caseId).order_by('-episodeDisplayID')
        if episodes:
            return episodes[0]
        else:
            return None

    @property
    @memoized
    def _adherences(self):
        return list(
            Adherence.objects.filter(episodeId=self._episode.episodeID).order_by('-doseDate')
        ) if self._episode else []

    @property
    @memoized
    def _prescriptions(self):
        return list(EpisodePrescription.objects.filter(beneficiaryId=self.beneficiary.caseId))

    @property
    @memoized
    def _labtests(self):
        if self._episode:
            return list(LabTest.objects.filter(episodeId=self._episode))
        else:
            return []

    @property
    @memoized
    def _agency(self):
        return (
            self._episode.treating_provider or self.beneficiary.referred_provider
            if self._episode else self.beneficiary.referred_provider
        )

    @property
    @memoized
    def _location_owner(self):
        if self.location_owner:
            return self.location_owner
        else:
            return SQLLocation.active_objects.get(
                domain=self.domain,
                site_code=str(self._agency.agencyId),
            )

    @property
    @memoized
    def _location_owner_id(self):
        return self._location_owner.location_id

    @property
    @memoized
    def _virtual_user(self):
        return CommCareUser.get(self._location_owner.user_id)

    @property
    @memoized
    def _id_issuer_number(self):
        return self._virtual_user.user_data['id_issuer_number']

    @property
    @memoized
    def _id_issuer_body(self):
        return self._virtual_user.user_data['id_issuer_body']

    @property
    def _id_device_body(self):
        return compress_nikshay_id(0, 0)

    @property
    @memoized
    def _serial_count(self):
        return MigratedBeneficiaryCounter.get_next_counter()

    @property
    @memoized
    def _serial_count_compressed(self):
        return compress_nikshay_id(self._serial_count, 2)

    @property
    @memoized
    def person_id_flat(self):
        return self._id_issuer_body + self._id_device_body + self._serial_count_compressed

    @property
    def person_id(self):
        num_chars_between_hyphens = 3
        return '-'.join([
            self.person_id_flat[i:i + num_chars_between_hyphens]
            for i in range(0, len(self.person_id_flat), num_chars_between_hyphens)
        ])
