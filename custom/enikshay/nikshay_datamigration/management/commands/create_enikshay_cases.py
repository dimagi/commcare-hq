from django.core.management import BaseCommand

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.nikshay_datamigration.models import PatientDetail, Outcome, Followup
from dimagi.utils.decorators.memoized import memoized


class EnikshayCaseFactory(object):

    domain = None
    patient_detail = None

    def __init__(self, domain, patient_detail):
        self.domain = domain
        self.patient_detail = patient_detail
        self.factory = CaseFactory(domain=domain)
        self.case_accessor = CaseAccessors(domain)

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
        return CaseStructure(
            attrs={
                'create': True,
                'case_type': 'person',
                # 'owner_id': self._location.location_id,
                'update': {
                    'nikshay_id': self.patient_detail.PregId,

                    'current_address_state_choice': self.patient_detail.scode,
                    'permanent_address_state_choice': self.patient_detail.scode,

                    'current_address_district_choice': self.patient_detail.Dtocode,
                    'permanent_address_district_choice': self.patient_detail.Dtocode,

                    'tu_choice': self.patient_detail.Tbunitcode,

                    'phi': self.patient_detail.PHI,

                    'name': self.patient_detail.pname,
                    'first_name': self.patient_detail.first_name,
                    'middle_name': self.patient_detail.middle_name,
                    'last_name': self.patient_detail.last_name,

                    'sex': self.patient_detail.sex,

                    'age_entered': self.patient_detail.page,

                    # poccupation

                    'aadhaar_number': self.patient_detail.paadharno,

                    'current_address': self.patient_detail.paddress, # not exactly clear which address field is right

                    # 'date_reported'

                    # 'mobile_number': self.patient_detail.pmob, # not used in eNikshay
                    'migration_created_case': True,
                },
            },
        )

    @memoized
    def occurrence(self, outcome):
        kwargs = {
            'attrs': {
                'create': True,
                'case_type': 'occurrence',
                'update': {
                    'nikshay_id': outcome.PatientId.PregId,
                    'hiv_status': outcome.HIVStatus,
                    'migration_created_case': True,
                },
            },
            'indices': [CaseIndex(
                self.person(),
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.person().attrs['case_type'],
            )],
        }

        for occurrence_case in self.case_accessor.get_cases([
            index.referenced_id for index in
            self.case_accessor.get_case(self.person().case_id).reverse_indices
        ]):
            if outcome.pk == occurrence_case.dynamic_case_properties().get('nikshay_id'):
                kwargs['case_id'] = occurrence_case.case_id
                kwargs['attrs']['create'] = False
                break

        return CaseStructure(**kwargs)

    @memoized
    def episode(self, outcome):
        kwargs = {
            'attrs': {
                'create': True,
                'case_type': 'episode',
                'update': {
                    'treatment_supporter_mobile_number': outcome.PatientId.cmob,

                    'date_reported': self.patient_detail.pregdate1, # is this right?

                    'disease_classification': self.patient_detail.dcexpulmunory,

                    'migration_created_case': True,

                    # poccupation
                },
            },
            'indices': [CaseIndex(
                self.occurrence(outcome),
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.occurrence(outcome).attrs['case_type'],
            )],
        }

        for episode_case in self.case_accessor.get_cases([
            index.referenced_id for index in
            self.case_accessor.get_case(self.occurrence(outcome).case_id).reverse_indices
        ]):
            if episode_case.dynamic_case_properties().get('migration_created_case'):
                kwargs['case_id'] = episode_case.case_id
                kwargs['attrs']['create'] = False
                break

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
                    'migration_followup_id': followup.id,
                    'migration_created_case': True,
                },
            },
            'indices': [CaseIndex(
                occurrence_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=occurrence_structure.attrs['case_type'],
            )],
        }

        for test_case in self.case_accessor.get_cases([
            index.referenced_id for index in
            self.case_accessor.get_case(occurrence_structure.case_id).reverse_indices
        ]):
            dynamic_case_properties = test_case.dynamic_case_properties()
            if 'migration_followup_id' in dynamic_case_properties and followup.id == int(test_case.dynamic_case_properties()['migration_followup_id']):
                kwargs['case_id'] = test_case.case_id
                kwargs['attrs']['create'] = False

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
        return self.nikshay_code_to_location(self.domain)[self._nikshay_code]

    @classmethod
    @memoized
    def nikshay_code_to_location(cls, domain):
        return {
            location.metadata.get('nikshay_code'): location
            for location in SQLLocation.objects.filter(domain=domain)
            if 'nikshay_code' in location.metadata
        }

    @property
    def _nikshay_code(self):
        return '-'.join(self.patient_detail.PregId.split('-')[:4])


class Command(BaseCommand):

    def handle(self, domain, **options):
        base_query = PatientDetail.objects.all()

        start = options['start']
        limit = options['limit']

        if limit is not None:
            patient_details = base_query[start:start + limit]
        else:
            patient_details = base_query[start:]

        counter = 0
        for patient_detail in patient_details:
            case_factory = EnikshayCaseFactory(domain, patient_detail)
            case_factory.create_cases()
            counter += 1
            print counter
        print 'All patient cases created'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--start',
            dest='start',
            default=0,
            type=int,
        )
        parser.add_argument(
            '--limit',
            dest='limit',
            default=None,
            type=int,
        )
