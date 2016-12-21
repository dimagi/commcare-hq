from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.nikshay_datamigration.models import Outcome, Followup


def validate_number(string_value):
    if string_value is None or string_value.strip() == '':
        return None
    else:
        return int(string_value)


class EnikshayCaseFactory(object):

    domain = None
    patient_detail = None

    def __init__(self, domain, patient_detail, nikshay_codes_to_location):
        self.domain = domain
        self.patient_detail = patient_detail
        self.factory = CaseFactory(domain=domain)
        self.case_accessor = CaseAccessors(domain)
        self.nikshay_codes_to_location = nikshay_codes_to_location

    def create_cases(self):
        self.create_person_case()
        self.create_occurrence_case()
        self.create_episode_case()
        self.create_test_cases()

    def create_person_case(self):
        person_structure = self.person()
        person_case = self.factory.create_or_update_case(person_structure)[0]
        person_structure.case_id = person_case.case_id

    def create_occurrence_case(self):
        if self._outcome:
            occurrence_structure = self.occurrence(self._outcome)
            occurrence_case = self.factory.create_or_update_case(occurrence_structure)[0]
            occurrence_structure.case_id = occurrence_case.case_id

    def create_episode_case(self):
        if self._outcome:
            episode_structure = self.episode(self._outcome)
            episode_case = self.factory.create_or_update_case(episode_structure)[0]
            episode_structure.case_id = episode_case.case_id

    def create_test_cases(self):
        if self._outcome:
            # how many followup's do not have a corresponding outcome? how should we handle this situation?
            self.factory.create_or_update_cases([self.test(followup) for followup in self._followups])

    @memoized
    def person(self):
        nikshay_id = self.patient_detail.PregId

        kwargs = {
            'attrs': {
                'case_type': 'person',
                'external_id': nikshay_id,
                # 'owner_id': self._location.location_id,
                'update': {
                    'aadhaar_number': self.patient_detail.paadharno,
                    'age': self.patient_detail.page,
                    'age_entered': self.patient_detail.page,
                    'contact_phone_number': validate_number(self.patient_detail.pmob),
                    'current_address': self.patient_detail.paddress,
                    'current_address_district_choice': self.patient_detail.Dtocode,
                    'current_address_state_choice': self.patient_detail.scode,
                    'dob_known': 'no',
                    'first_name': self.patient_detail.first_name,
                    'last_name': self.patient_detail.last_name,
                    'middle_name': self.patient_detail.middle_name,
                    'name': self.patient_detail.pname,
                    'nikshay_id': nikshay_id,
                    'permanent_address_district_choice': self.patient_detail.Dtocode,
                    'permanent_address_state_choice': self.patient_detail.scode,
                    'phi': self.patient_detail.PHI,
                    'secondary_contact_name_address': (
                        (self.patient_detail.cname or '')
                        + ', '
                        + (self.patient_detail.caddress or '')
                    ),
                    'secondary_contact_phone_number': validate_number(self.patient_detail.cmob),
                    'sex': self.patient_detail.sex,
                    'tu_choice': self.patient_detail.Tbunitcode,

                    'migration_created_case': 'true',
                },
            },
        }

        matching_external_ids = self.case_accessor.get_cases_by_external_id(nikshay_id, case_type='person')
        assert len(matching_external_ids) <= 1
        if matching_external_ids:
            kwargs['case_id'] = matching_external_ids[0].case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    @memoized
    def occurrence(self, outcome):
        kwargs = {
            'attrs': {
                'case_type': 'occurrence',
                'update': {
                    'hiv_status': outcome.HIVStatus,
                    'name': 'Occurrence #1',
                    'nikshay_id': self.patient_detail.PregId,
                    'occurrence_episode_count': 1,

                    'migration_created_case': 'true',
                },
            },
            'indices': [CaseIndex(
                self.person(),
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.person().attrs['case_type'],
            )],
        }

        matching_occurrence_case = next((
            occurrence_case for occurrence_case in self.case_accessor.get_cases([
                index.referenced_id for index in
                self.case_accessor.get_case(self.person().case_id).reverse_indices
            ])
            if outcome.pk == occurrence_case.dynamic_case_properties().get('nikshay_id')
        ), None)
        if matching_occurrence_case:
            kwargs['case_id'] = matching_occurrence_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    @memoized
    def episode(self, outcome):
        kwargs = {
            'attrs': {
                'case_type': 'episode',
                'update': {
                    'date_reported': self.patient_detail.pregdate1,  # is this right?
                    'disease_classification': self.patient_detail.disease_classification,
                    'patient_type_choice': self.patient_detail.patient_type_choice,
                    'treatment_supporter_designation': self.patient_detail.treatment_supporter_designation,
                    'treatment_supporter_first_name': self.patient_detail.treatment_supporter_first_name,
                    'treatment_supporter_last_name': self.patient_detail.treatment_supporter_last_name,
                    'treatment_supporter_mobile_number': validate_number(self.patient_detail.dotmob),

                    'migration_created_case': 'true',
                },
            },
            'indices': [CaseIndex(
                self.occurrence(outcome),
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.occurrence(outcome).attrs['case_type'],
            )],
        }

        matching_episode_case = next((
            extension_case for extension_case in self.case_accessor.get_cases([
                index.referenced_id for index in
                self.case_accessor.get_case(self.occurrence(outcome).case_id).reverse_indices
            ])
            if (
                extension_case.type == 'episode'
                and extension_case.dynamic_case_properties().get('migration_created_case')
            )
        ), None)
        if matching_episode_case:
            kwargs['case_id'] = matching_episode_case.case_id
            kwargs['attrs']['create'] = False
        else:
            kwargs['attrs']['create'] = True

        return CaseStructure(**kwargs)

    @memoized
    def test(self, followup):
        occurrence_structure = self.occurrence(self._outcome)  # TODO - pass outcome as argument

        kwargs = {
            'attrs': {
                'create': True,
                'case_type': 'test',
                'update': {
                    'date_tested': followup.TestDate,

                    'migration_created_case': 'true',
                    'migration_followup_id': followup.id,
                },
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=occurrence_structure.attrs['case_type'],
            )],
        }

        matching_test_case = next((
            extension_case for extension_case in self.case_accessor.get_cases([
                index.referenced_id for index in
                self.case_accessor.get_case(occurrence_structure.case_id).reverse_indices
            ])
            if (
                extension_case.type == 'test'
                and followup.id == int(extension_case.dynamic_case_properties().get('migration_followup_id', -1))
            )
        ), None)
        if matching_test_case:
            kwargs['case_id'] = matching_test_case.case_id
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
        return Followup.objects.filter(PatientID=self.patient_detail)

    @property
    def _location(self):
        return self.nikshay_codes_to_location[self._nikshay_code]

    @property
    def _nikshay_code(self):
        return '-'.join(self.patient_detail.PregId.split('-')[:4])


def get_nikshay_codes_to_location(domain):
    return {
        location.metadata.get('nikshay_code'): location
        for location in SQLLocation.objects.filter(domain=domain)
        if 'nikshay_code' in location.metadata
    }
