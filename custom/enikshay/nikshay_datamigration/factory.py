from collections import namedtuple
from datetime import date, datetime

from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID, CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseStructure, CaseIndex
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import get_open_occurrence_case_from_person, get_open_episode_case_from_occurrence
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.nikshay_datamigration.models import Outcome


PERSON_CASE_TYPE = 'person'
OCCURRENCE_CASE_TYPE = 'occurrence'
EPISODE_CASE_TYPE = 'episode'

MockLocation = namedtuple('MockLocation', 'name location_id location_type')
MockLocationType = namedtuple('MockLocationType', 'name code')


def validate_phone_number(string_value):
    if string_value is None or string_value.strip() in ['', '0']:
        return ''
    else:
        phone_number = str(int(string_value))
        assert len(phone_number) == 10
        return phone_number


class EnikshayCaseFactory(object):

    domain = None
    patient_detail = None

    def __init__(self, domain, patient_detail, nikshay_codes_to_location, test_phi=None):
        self.domain = domain
        self.patient_detail = patient_detail
        self.case_accessor = CaseAccessors(domain)
        self.nikshay_codes_to_location = nikshay_codes_to_location
        self.test_phi = test_phi

    @property
    def nikshay_id(self):
        return self.patient_detail.PregId

    @property
    @memoized
    def existing_person_case(self):
        """
        Get the existing person case for this nikshay ID, or None if no person case exists
        """
        matching_external_ids = self.case_accessor.get_cases_by_external_id(self.nikshay_id, case_type='person')
        if matching_external_ids:
            assert len(matching_external_ids) == 1
            return matching_external_ids[0]
        return None

    @property
    def creating_person_case(self):
        return self.existing_person_case is not None

    @property
    @memoized
    def existing_occurrence_case(self):
        """
        Get the existing occurrence case for this nikshay ID, or None if no occurrence case exists
        """
        if self.existing_person_case:
            try:
                return get_open_occurrence_case_from_person(
                    self.domain, self.existing_person_case.case_id
                )
            except ENikshayCaseNotFound:
                return None

    @property
    @memoized
    def existing_episode_case(self):
        """
        Get the existing episode case for this nikshay ID, or None if no episode case exists
        """
        if self.existing_occurrence_case:
            try:
                return get_open_episode_case_from_occurrence(
                    self.domain, self.existing_occurrence_case.case_id
                )
            except ENikshayCaseNotFound:
                return None

    def get_case_structures_to_create(self):
        person_structure = self.get_person_case_structure()
        ocurrence_structure = self.get_occurrence_case_structure(person_structure)
        episode_structure = self.get_episode_case_structure(ocurrence_structure)
        return [episode_structure]

    def get_person_case_structure(self):
        kwargs = {
            'attrs': {
                'case_type': PERSON_CASE_TYPE,
                'external_id': self.nikshay_id,
                'update': {
                    'age': self.patient_detail.page,
                    'age_entered': self.patient_detail.page,
                    'contact_phone_number': validate_phone_number(self.patient_detail.pmob),
                    'current_address': self.patient_detail.paddress,
                    'dob': date(date.today().year - self.patient_detail.page, 7, 1),
                    'dob_known': 'no',
                    'first_name': self.patient_detail.first_name,
                    'last_name': self.patient_detail.last_name,
                    'name': self.patient_detail.pname,
                    'person_id': 'N-' + self.nikshay_id,
                    'secondary_contact_name_address': (
                        (self.patient_detail.cname or '')
                        + ', '
                        + (self.patient_detail.caddress or '')
                    ),
                    'secondary_contact_phone_number': validate_phone_number(self.patient_detail.cmob),
                    'sex': self.patient_detail.sex,

                    'migration_created_case': 'true',
                },
            },
        }

        if self.phi:
            if self.phi.location_type.code == 'phi':
                kwargs['attrs']['owner_id'] = self.phi.location_id
                kwargs['attrs']['update']['phi'] = self.phi.name
                kwargs['attrs']['update']['tu_choice'] = self.tu.name
                kwargs['attrs']['update']['current_address_district_choice'] = self.district.location_id
                kwargs['attrs']['update']['current_address_state_choice'] = self.state.location_id
            else:
                kwargs['attrs']['owner_id'] = ARCHIVED_CASE_OWNER_ID
                kwargs['attrs']['update']['archive_reason'] = 'migration_not_phi_location'
                kwargs['attrs']['update']['migration_error'] = 'not_phi_location'
                kwargs['attrs']['update']['migration_error_details'] = self._nikshay_code
        else:
            kwargs['attrs']['owner_id'] = ARCHIVED_CASE_OWNER_ID
            kwargs['attrs']['update']['archive_reason'] = 'migration_location_not_found'
            kwargs['attrs']['update']['migration_error'] = 'location_not_found'
            kwargs['attrs']['update']['migration_error_details'] = self._nikshay_code

        if self._outcome and self._outcome.hiv_status:
            kwargs['attrs']['update']['hiv_status'] = self._outcome.hiv_status
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
                    'occurrence_id': datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3],
                    'migration_created_case': 'true',
                },
            },
            'indices': [CaseIndex(
                person_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=PERSON_CASE_TYPE,
            )],
        }

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
        kwargs = {
            'attrs': {
                'case_type': EPISODE_CASE_TYPE,
                'date_opened': self.patient_detail.pregdate1,
                'owner_id': '-',
                'update': {
                    'adherence_schedule_date_start': self.patient_detail.treatment_initiation_date,
                    'date_of_diagnosis': self.patient_detail.pregdate1,
                    'date_of_mo_signature': self.patient_detail.date_of_mo_signature,
                    'disease_classification': self.patient_detail.disease_classification,
                    'dots_99_enabled': 'false',
                    'episode_pending_registration': 'no',
                    'episode_type': 'confirmed_tb',
                    'name': 'Episode #1: Confirmed TB (Patient)',
                    'nikshay_id': self.nikshay_id,
                    'occupation': self.patient_detail.occupation,
                    'patient_type_choice': self.patient_detail.patient_type_choice,
                    'treatment_initiated': 'yes_phi',
                    'treatment_initiation_date': self.patient_detail.treatment_initiation_date,
                    'treatment_supporter_designation': self.patient_detail.treatment_supporter_designation,
                    'treatment_supporter_first_name': self.patient_detail.treatment_supporter_first_name,
                    'treatment_supporter_last_name': self.patient_detail.treatment_supporter_last_name,
                    'treatment_supporter_mobile_number': validate_phone_number(self.patient_detail.dotmob),

                    'migration_created_case': 'true',
                },
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=OCCURRENCE_CASE_TYPE,
            )],
        }

        if self.patient_detail.disease_classification == 'extra_pulmonary':
            kwargs['attrs']['update']['site_choice'] = self.patient_detail.site_choice

        if self.existing_episode_case:
            kwargs['case_id'] = self.existing_episode_case.case_id
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
    def state(self):
        if self.test_phi is not None:
            return MockLocation('FAKESTATE', 'fake_state_id', MockLocationType('state', 'state'))
        return self.nikshay_codes_to_location.get(self.patient_detail.PregId.split('-')[0])

    @property
    def district(self):
        if self.test_phi is not None:
            return MockLocation('FAKEDISTRICT', 'fake_district_id', MockLocationType('district', 'district'))

        return self.nikshay_codes_to_location.get('-'.join(self.patient_detail.PregId.split('-')[:2]))

    @property
    def tu(self):
        if self.test_phi is not None:
            return MockLocation('FAKETU', 'fake_tu_id', MockLocationType('tu', 'tu'))
        return self.nikshay_codes_to_location.get('-'.join(self.patient_detail.PregId.split('-')[:3]))

    @property
    def phi(self):
        if self.test_phi is not None:
            return MockLocation('FAKEPHI', self.test_phi, MockLocationType('phi', 'phi'))
        return self.nikshay_codes_to_location.get(self._nikshay_code)

    @property
    def _nikshay_code(self):
        return '-'.join(self.patient_detail.PregId.split('-')[:4])


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
