from django.core.management import BaseCommand
from django.db import transaction

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL

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

    @transaction.atomic
    def create_cases(self):
        self.create_person_case()
        self.create_occurrence_cases()
        self.create_episode_cases()
        self.create_test_cases()

    def create_person_case(self):
        self.factory.create_or_update_case(self.person())

    def create_occurrence_cases(self):
        occurrences = [self.occurrence(outcome) for outcome in self._outcomes]
        cases = self.factory.create_or_update_cases(occurrences)
        for occurrence_structure, occurrence_case in zip(occurrences, cases):
            occurrence_structure.case_id = occurrence_case.case_id

    def create_episode_cases(self):
        episodes = [self.episode(outcome) for outcome in self._outcomes]
        cases = self.factory.create_or_update_cases(episodes)
        for episode_structure, episode_case in zip(episodes, cases):
            episode_structure.case_id = episode_case.case_id

    def create_test_cases(self):
        tests = [
            self.test(followup) for followup in self._followups
            if Outcome.objects.filter(PatientId=followup.PatientID).exists()
            # how many followup's do not have a corresponding outcome? how should we handle this situation?
        ]
        self.factory.create_or_update_cases(tests)

    @memoized
    def person(self):
        return CaseStructure(
            case_id=self.patient_detail.PregId,
            attrs={
                'create': True,
                'case_type': 'person',
                'owner_id': self._location.location_id,
                'update': {
                    'name': self.patient_detail.pname,
                    'aadhaar_number': self.patient_detail.paadharno,
                    'phi': self.patient_detail.PHI,
                    'first_name': self.patient_detail.first_name,
                    'middle_name': self.patient_detail.middle_name,
                    'last_name': self.patient_detail.last_name,
                    'age': self.patient_detail.page,
                    'sex': self.patient_detail.sex,
                    'current_address': self.patient_detail.paddress,
                    'mobile_number': self.patient_detail.pmob,
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
            index.case_id for index in
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
                    'migration_created_case': True,
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
            index.case_id for index in
            self.case_accessor.get_case(self.occurrence(outcome).case_id).reverse_indices
        ]):
            if episode_case.dynamic_case_properties().get('migration_created_case'):
                kwargs['case_id'] = episode_case.case_id
                kwargs['attrs']['create'] = False
                break

        return CaseStructure(**kwargs)

    @memoized
    def test(self, followup):
        episode_structure = self.episode(
            Outcome.objects.get(PatientId=followup.PatientID)
        )

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
                episode_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=episode_structure.attrs['case_type'],
            )],
        }

        for test_case in self.case_accessor.get_cases([
            index.case_id for index in
            self.case_accessor.get_case(episode_structure.case_id).reverse_indices
        ]):
            if followup.id == int(test_case.dynamic_case_properties().get('migration_followup_id')):
                kwargs['case_id'] = test_case.case_id
                kwargs['attrs']['create'] = False

        return CaseStructure(**kwargs)

    @property
    @memoized
    def _outcomes(self):
        return Outcome.objects.filter(PatientId=self.patient_detail)

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

    def handle(self, domain, *args, **options):
        counter = 0
        for patient_detail in PatientDetail.objects.all():
            case_factory = EnikshayCaseFactory(domain, patient_detail)
            case_factory.create_cases()
            counter += 1
            print counter
        print 'All patient cases created'
