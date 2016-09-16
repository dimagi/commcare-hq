from django.core.management import BaseCommand

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex

from custom.enikshay.nikshay_datamigration.models import PatientDetail, Outcome

ENIKSHAY_DOMAIN = 'enikshay-np'


class EnikshayCaseFactory(object):

    patient_detail = None

    def __init__(self, patient_detail):
        self.patient_detail = patient_detail
        self.factory = CaseFactory(domain=ENIKSHAY_DOMAIN)

    def create_cases(self):
        self.create_person_case()
        self.create_occurrence_cases()

    def create_person_case(self):
        self.factory.create_or_update_case(self.person)

    def create_occurrence_cases(self):
        self.factory.create_or_update_cases([
            self.occurrence(outcome)
            for outcome in Outcome.objects.filter(PatientId=self.patient_detail)
        ])

    @property
    def person(self):
        return CaseStructure(
            case_id=self.patient_detail.PregId,
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

    def create_case(self, case_structure):
        return self.factory.create_or_update_cases([case_structure])


class Command(BaseCommand):

    def handle(self, *args, **options):
        counter = 0
        for patient_detail in PatientDetail.objects.all():
            case_factory = EnikshayCaseFactory(patient_detail)
            case_factory.create_cases()
            counter += 1
            print counter
        print 'All patient cases created'
