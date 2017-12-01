from __future__ import absolute_import
from collections import namedtuple
from datetime import date, datetime

from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID, CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import (
    get_first_parent_of_case,
    get_open_drtb_hiv_case_from_occurrence,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound, ENikshayLocationNotFound
from custom.enikshay.nikshay_datamigration.exceptions import MatchingNikshayIdCaseNotMigrated
from custom.enikshay.nikshay_datamigration.models import (
    Followup,
    Outcome,
)

PERSON_CASE_TYPE = 'person'
OCCURRENCE_CASE_TYPE = 'occurrence'
EPISODE_CASE_TYPE = 'episode'
DRTB_HIV_REFERRAL_CASE_TYPE = 'drtb-hiv-referral'
TEST_CASE_TYPE = 'test'

MockLocation = namedtuple('MockLocation', 'name location_id location_type')
MockLocationType = namedtuple('MockLocationType', 'name code')


def validate_phone_number(string_value):
    if string_value is None or string_value.strip() in ['', '0']:
        return ''
    else:
        string_value = string_value.strip()
        assert string_value.isdigit()

        if len(string_value) == 11 and string_value[0] == '0':
            string_value = string_value[1:]

        assert 8 <= len(string_value) <= 10
        return string_value


def get_human_friendly_id():
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]


class EnikshayCaseFactory(object):

    domain = None
    patient_detail = None

    def __init__(self, domain, migration_comment, patient_detail, nikshay_codes_to_location, test_phi=None):
        self.domain = domain
        self.migration_comment = migration_comment
        self.patient_detail = patient_detail
        self.case_accessor = CaseAccessors(domain)
        self.nikshay_codes_to_location = nikshay_codes_to_location
        self.test_phi = test_phi

    @property
    def nikshay_id(self):
        return self.patient_detail.PregId

    @property
    @memoized
    def existing_episode_case(self):
        """
        Get the existing episode case for this nikshay ID, or None if no episode case exists
        """
        matching_external_ids = self.case_accessor.get_cases_by_external_id(
            self.nikshay_id, case_type=EPISODE_CASE_TYPE
        )
        if matching_external_ids:
            assert len(matching_external_ids) == 1
            existing_episode = matching_external_ids[0]
            if existing_episode.dynamic_case_properties().get('migration_created_case') != 'true':
                raise MatchingNikshayIdCaseNotMigrated
            return matching_external_ids[0]
        return None

    @property
    @memoized
    def existing_occurrence_case(self):
        """
        Get the existing occurrence case for this nikshay ID, or None if no occurrence case exists
        """
        if self.existing_episode_case:
            try:
                return get_first_parent_of_case(
                    self.domain, self.existing_episode_case.case_id, OCCURRENCE_CASE_TYPE
                )
            except ENikshayCaseNotFound:
                return None

    @property
    @memoized
    def existing_person_case(self):
        """
        Get the existing person case for this nikshay ID, or None if no episode case exists
        """
        if self.existing_occurrence_case:
            try:
                return get_first_parent_of_case(
                    self.domain, self.existing_occurrence_case.case_id, PERSON_CASE_TYPE
                )
            except ENikshayCaseNotFound:
                return None

    @property
    @memoized
    def existing_drtb_hiv_case(self):
        """
        Get the existing secondary owner case for the occurrence case,
        or None if no occurrence case exists
        """
        if self.existing_occurrence_case:
            try:
                return get_open_drtb_hiv_case_from_occurrence(
                    self.domain, self.existing_occurrence_case.case_id
                )
            except ENikshayCaseNotFound:
                return None

    @memoized
    def existing_test_case(self, followup):
        #  TODO
        return None

    def get_case_structures_to_create(self):
        person_structure = self.get_person_case_structure()
        occurrence_structure = self.get_occurrence_case_structure(person_structure)
        episode_structure = self.get_episode_case_structure(occurrence_structure)
        test_structures = [
            self.get_test_case_structure(followup, occurrence_structure)
            for followup in self._followups
        ]
        if (
            not self._outcome
            or (not self._outcome.is_treatment_ended and self._outcome.hiv_status in ['unknown', 'reactive'])
        ):
            drtb_hiv_referral_structure = self.get_drtb_hiv_referral_case_structure(episode_structure)
            return [drtb_hiv_referral_structure] + test_structures
        else:
            return [episode_structure] + test_structures

    def get_person_case_structure(self):
        kwargs = {
            'attrs': {
                'case_type': PERSON_CASE_TYPE,
                'update': {
                    'age': self.patient_detail.page,
                    'age_entered': self.patient_detail.page,
                    'contact_phone_number': '91' + validate_phone_number(self.patient_detail.pmob),
                    'current_address': self.patient_detail.paddress,
                    'current_episode_type': 'confirmed_tb',
                    'current_patient_type_choice': self.patient_detail.patient_type_choice,
                    'dataset': 'real',
                    'dob': date(date.today().year - self.patient_detail.page, 7, 1),
                    'dob_known': 'no',
                    'has_open_tests': 'no',
                    'hiv_status': self._outcome.hiv_status if self._outcome else 'unknown',
                    'first_name': self.patient_detail.first_name,
                    'last_name': self.patient_detail.last_name,
                    'name': self.patient_detail.pname,
                    'person_id': self.patient_detail.person_id,
                    'phone_number': validate_phone_number(self.patient_detail.pmob),
                    'secondary_contact_name_address': (
                        (self.patient_detail.cname or '')
                        + ', '
                        + (self.patient_detail.caddress or '')
                    ),
                    'secondary_contact_phone_number': validate_phone_number(self.patient_detail.cmob),
                    'sex': self.patient_detail.sex,

                    'migration_comment': self.migration_comment,
                    'migration_created_case': 'true',
                    'migration_created_from_record': self.patient_detail.PregId,
                },
            },
        }

        if self.phi.location_type.code == 'phi':
            kwargs['attrs']['owner_id'] = self.phi.location_id
            kwargs['attrs']['update']['phi'] = self.phi.name
            kwargs['attrs']['update']['phi_assigned_to'] = self.phi.location_id
            kwargs['attrs']['update']['tu_choice'] = self.tu.location_id
        else:
            kwargs['attrs']['owner_id'] = ARCHIVED_CASE_OWNER_ID
            kwargs['attrs']['update']['archive_reason'] = 'migration_not_phi_location'
            kwargs['attrs']['update']['migration_error'] = 'not_phi_location'
            kwargs['attrs']['update']['migration_error_details'] = self._phi_code

        if self._outcome:
            if self._outcome.hiv_status:
                kwargs['attrs']['update']['hiv_status'] = self._outcome.hiv_status
            if self._outcome.is_treatment_ended:
                kwargs['attrs']['owner_id'] = ARCHIVED_CASE_OWNER_ID
                kwargs['attrs']['update']['is_active'] = 'no'
            else:
                kwargs['attrs']['update']['is_active'] = 'yes'
            if self._outcome.treatment_outcome == 'died':
                kwargs['attrs']['close'] = True
        else:
            kwargs['attrs']['update']['is_active'] = 'yes'

        if self.patient_detail.paadharno is not None:
            kwargs['attrs']['update']['aadhaar_number'] = self.patient_detail.paadharno

        if self.existing_person_case is not None:
            kwargs['case_id'] = self.existing_person_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    def get_occurrence_case_structure(self, person_structure):
        """
        This gets the occurrence case structure with a nested person case structure.
        """
        kwargs = {
            'attrs': {
                'case_type': OCCURRENCE_CASE_TYPE,
                'owner_id': '-',
                'update': {
                    'current_episode_type': 'confirmed_tb',
                    'ihv_date': self.patient_detail.ihv_date,
                    'initial_home_visit_status': self.patient_detail.initial_home_visit_status,
                    'name': 'Occurrence #1',
                    'occurrence_episode_count': 1,
                    'occurrence_id': get_human_friendly_id(),

                    'migration_comment': self.migration_comment,
                    'migration_created_case': 'true',
                    'migration_created_from_record': self.patient_detail.PregId,
                },
            },
            'indices': [CaseIndex(
                person_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=PERSON_CASE_TYPE,
            )],
        }

        if self._outcome:
            if self._outcome.is_treatment_ended:
                kwargs['attrs']['close'] = True

        if self.existing_occurrence_case:
            kwargs['case_id'] = self.existing_occurrence_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    def get_episode_case_structure(self, occurrence_structure):
        """
        This gets the episode case structure with a nested occurrence and person case structures
        inside of it.
        """
        treatment_initiation_date = (
            self.patient_detail.treatment_initiation_date
            if self.patient_detail.treatment_initiation_date
            else self.patient_detail.pregdate1
        )
        kwargs = {
            'attrs': {
                'case_type': EPISODE_CASE_TYPE,
                'date_opened': self.patient_detail.pregdate1,
                'external_id': self.nikshay_id,
                'owner_id': '-',
                'update': {
                    'adherence_schedule_date_start': treatment_initiation_date,
                    'adherence_schedule_id': 'schedule_mwf',
                    'date_of_diagnosis': treatment_initiation_date,
                    'date_of_mo_signature': (
                        self.patient_detail.date_of_mo_signature
                        if self.patient_detail.date_of_mo_signature
                        else self.patient_detail.pregdate1
                    ),
                    'disease_classification': self.patient_detail.disease_classification,
                    'dots_99_enabled': 'false',
                    'episode_id': get_human_friendly_id(),
                    'episode_pending_registration': 'no',
                    'episode_type': 'confirmed_tb',
                    'name': 'Episode #1: Confirmed TB (Patient)',
                    'nikshay_id': self.nikshay_id,
                    'occupation': self.patient_detail.occupation,
                    'patient_type_choice': self.patient_detail.patient_type_choice,
                    'transfer_in': 'yes' if self.patient_detail.patient_type_choice == 'transfer_in' else 'no',
                    'treatment_card_completed_date': self.patient_detail.pregdate1,
                    'treatment_initiated': 'yes_phi',
                    'treatment_initiation_date': treatment_initiation_date,
                    'treatment_supporter_designation': self.patient_detail.treatment_supporter_designation,
                    'treatment_supporter_first_name': self.patient_detail.treatment_supporter_first_name,
                    'treatment_supporter_last_name': self.patient_detail.treatment_supporter_last_name,
                    'treatment_supporter_mobile_number': validate_phone_number(self.patient_detail.dotmob),

                    'migration_comment': self.migration_comment,
                    'migration_created_case': 'true',
                    'migration_created_from_record': self.patient_detail.PregId,
                },
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }

        if self.phi.location_type.code == 'phi':
            phi_location_id = self.phi.location_id
            kwargs['attrs']['update']['diagnosing_facility_id'] = phi_location_id
            kwargs['attrs']['update']['treatment_initiating_facility_id'] = phi_location_id

        if self.patient_detail.disease_classification == 'extra_pulmonary':
            kwargs['attrs']['update']['site_choice'] = self.patient_detail.site_choice
        if self._outcome:
            if self._outcome.treatment_outcome:
                kwargs['attrs']['update']['treatment_outcome'] = self._outcome.treatment_outcome
                assert self._outcome.treatment_outcome_date is not None
                kwargs['attrs']['update']['treatment_outcome_date'] = self._outcome.treatment_outcome_date
            if self._outcome.is_treatment_ended:
                kwargs['attrs']['close'] = True

        if self.existing_episode_case:
            kwargs['case_id'] = self.existing_episode_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    def get_drtb_hiv_referral_case_structure(self, episode_structure):
        kwargs = {
            'attrs': {
                'case_type': DRTB_HIV_REFERRAL_CASE_TYPE,
                'owner_id': self.drtb_hiv.location_id,
                'update': {
                    'name': self.patient_detail.pname,

                    'migration_comment': self.migration_comment,
                    'migration_created_case': 'true',
                    'migration_created_from_record': self.patient_detail.PregId,
                }
            },
            'indices': [CaseIndex(
                episode_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=EPISODE_CASE_TYPE,
            )],
        }
        if self.existing_drtb_hiv_case:
            kwargs['case_id'] = self.existing_drtb_hiv_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True
        return CaseStructure(**kwargs)

    def get_test_case_structure(self, followup, occurrence_structure):
        kwargs = {
            'attrs': {
                'case_type': TEST_CASE_TYPE,
                'close': False,
                'date_opened': followup.TestDate,
                'owner_id': '-',
                'update': {
                    'date_reported': followup.TestDate,
                    'date_tested': followup.TestDate,
                    'episode_type_at_request': 'presumptive_tb' if followup.IntervalId == 0 else 'confirmed_tb',
                    'lab_serial_number': followup.LabNo or '',
                    'name': followup.TestDate,
                    'result_grade': followup.result_grade,
                    'result_recorded': 'yes',
                    'testing_facility_id': followup.DMC,

                    'migration_comment': self.migration_comment,
                    'migration_created_case': 'true',
                    'migration_created_from_id': followup.id,
                    'migration_created_from_record': self.patient_detail.PregId,
                }
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }

        if followup.IntervalId == 0:
            kwargs['attrs']['update']['diagnostic_test_reason'] = 'presumptive_tb'
            kwargs['attrs']['update']['purpose_of_testing'] = 'diagnostic'
        elif followup.IntervalId == 1:
            kwargs['attrs']['update']['follow_up_test_reason'] = 'end_of_ip'
            kwargs['attrs']['update']['purpose_of_testing'] = 'follow_up'
        elif followup.IntervalId == 4:
            kwargs['attrs']['update']['follow_up_test_reason'] = 'end_of_cp'
            kwargs['attrs']['update']['purpose_of_testing'] = 'follow_up'

        existing_test_case = self.existing_test_case(followup)
        if existing_test_case:
            kwargs['case_id'] = existing_test_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True
        return CaseStructure(**kwargs)

    @property
    @memoized
    def _outcome(self):
        zero_or_one_outcomes = list(Outcome.objects.filter(PatientId=self.patient_detail))
        if zero_or_one_outcomes:
            return zero_or_one_outcomes[0]
        else:
            return None

    @property
    @memoized
    def _followups(self):
        return list(Followup.objects.filter(PatientID=self.patient_detail))

    @property
    def tu(self):
        if self.test_phi is not None:
            return MockLocation('FAKETU', 'fake_tu_id', MockLocationType('tu', 'tu'))

        tu_code = '-'.join(self._phi_code.split('-')[:3])
        try:
            return self.nikshay_codes_to_location[tu_code]
        except KeyError:
            raise ENikshayLocationNotFound(tu_code)

    @property
    def phi(self):
        if self.test_phi is not None:
            return MockLocation('FAKEPHI', self.test_phi, MockLocationType('phi', 'phi'))

        try:
            return self.nikshay_codes_to_location[self._phi_code]
        except KeyError:
            raise ENikshayLocationNotFound(self._phi_code)

    @property
    def drtb_hiv(self):
        if self.test_phi is not None:
            return MockLocation('FAKEDRTBHIV', 'fake_drtb_hiv_id', MockLocationType('drtb_hiv', 'drtb_hiv'))

        dto_code = '-'.join(self._phi_code.split('-')[:2])
        try:
            dto = self.nikshay_codes_to_location[dto_code]
        except KeyError:
            raise ENikshayLocationNotFound(dto_code)

        for dto_child in dto.get_children():
            if dto_child.location_type.code == 'drtb-hiv':
                return dto_child
        raise ENikshayLocationNotFound('drtb-hiv matching DTO %s' % dto_code)

    @property
    def _phi_code(self):
        return '%s-%s-%d-%d' % (
            self.patient_detail.scode,
            self.patient_detail.Dtocode,
            self.patient_detail.Tbunitcode,
            self.patient_detail.PHI,
        )


def get_nikshay_codes_to_location(domain):
    """
    Assuming that if a phi has a nikshay-code, its TU, DTO, and STO do too
    """
    return {
        nikshay_code: location
        for phi in SQLLocation.objects.filter(domain=domain).filter(location_type__code='phi')
        for nikshay_code, location in _get_all_nikshay_codes(phi)
        if 'nikshay_code' in phi.metadata
    }


def _get_all_nikshay_codes(phi):
    tu = phi.parent
    dto = tu.parent
    sto = dto.parent.parent

    phi_code = phi.metadata.get('nikshay_code')
    tu_code = tu.metadata.get('nikshay_code')
    dto_code = dto.metadata.get('nikshay_code')
    sto_code = sto.metadata.get('nikshay_code')

    return [
        (
            "%s-%s-%s-%s" % (sto_code, dto_code, tu_code, phi_code),
            phi
        ),
        (
            "%s-%s-%s" % (sto_code, dto_code, tu_code),
            tu
        ),
        (
            "%s-%s" % (sto_code, dto_code),
            dto
        ),
        (
            "%s" % sto_code,
            sto
        ),
    ]
