from django.core.management import BaseCommand

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex

from custom.enikshay.nikshay_datamigration.models import PatientDetail, Outcome, Followup
from dimagi.utils.decorators.memoized import memoized

ENIKSHAY_DOMAIN = 'enikshay-np'


class EnikshayCaseFactory(object):

    patient_detail = None

    def __init__(self, patient_detail):
        self.patient_detail = patient_detail
        self.factory = CaseFactory(domain=ENIKSHAY_DOMAIN)

    def create_cases(self):
        self.create_person_case()
        self.create_occurrence_cases()
        self.create_episode_cases()
        self.create_test_cases()

    def create_person_case(self):
        self.factory.create_or_update_case(self.person)

    def create_occurrence_cases(self):
        occurrences = [self.occurrence(outcome) for outcome in self.outcomes]
        cases = self.factory.create_or_update_cases(occurrences)
        for occurrence_structure, occurrence_case in zip(occurrences, cases):
            occurrence_structure.case_id = occurrence_case.case_id

    def create_episode_cases(self):
        episodes = [self.episode(outcome) for outcome in self.outcomes]
        cases = self.factory.create_or_update_cases(episodes)
        for episode_structure, episode_case in zip(episodes, cases):
            episode_structure.case_id = episode_case.case_id

    def create_test_cases(self):
        tests = [self.test(followup) for followup in self.followups]
        self.factory.create_or_update_cases(tests)

    @property
    @memoized
    def person(self):
        return CaseStructure(
            case_id=self.patient_detail.PregId,
            # owner_id: function of stocode, dtocode, tbunitcode, phi; then decide if dmc
            attrs={
                'create': True,
                'case_type': 'person',
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
                },
            },
        )

    @memoized
    def occurrence(self, outcome):
        return CaseStructure(
            attrs={
                'create': True,
                'case_type': 'occurrence',
                'update': {
                    'nikshay_id': outcome.PatientId.PregId,
                    'hiv_status': outcome.HIVStatus,
                },
            },
            indices=[CaseIndex(
                self.person,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.person.attrs['case_type'],
            )],
        )

    @memoized
    def episode(self, outcome):
        return CaseStructure(
            attrs={
                'create': True,
                'case_type': 'episode',
                'update': {
                    'treatment_supporter_mobile_number': outcome.PatientId.cmob,
                },
            },
            indices=[CaseIndex(
                self.occurrence(outcome),
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.occurrence(outcome).attrs['case_type'],
            )],
        )

    def test(self, followup):
        episode_structure = self.episode(
            Outcome.objects.get(PatientId=followup.PatientID)
        )
        return CaseStructure(
            attrs={
                'create': True,
                'case_type': 'test',
                'update': {
                    'date_tested': followup.TestDate,
                },
            },
            indices=[CaseIndex(
                episode_structure,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=episode_structure.attrs['case_type'],
            )],
        )

    @property
    def outcomes(self):
        return Outcome.objects.filter(PatientId=self.patient_detail)

    @property
    def followups(self):
        return [
            followup for followup in Followup.objects.filter(PatientID=self.patient_detail)
            if Outcome.objects.filter(PatientId=followup.PatientID).exists()
            # how many followup's do not have a corresponding outcome? how should we handle this situation?
        ]


class Command(BaseCommand):

    def handle(self, *args, **options):
        counter = 0
        for patient_detail in PatientDetail.objects.all():
            case_factory = EnikshayCaseFactory(patient_detail)
            case_factory.create_cases()
            counter += 1
            print counter
        print 'All patient cases created'
