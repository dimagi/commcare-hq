from django.core.management import BaseCommand

from dimagi.utils import make_uuid

from corehq.util.test_utils import create_and_save_a_case

from custom.enikshay.nikshay_datamigration.models import PatientDetail, Outcome


class CaseFactory(object):

    patient_detail = None

    def __init__(self, patient_detail):
        self.patient_detail = patient_detail

    def create_cases(self):
        self.create_person_case()
        self.create_occurrence_cases()

    def create_person_case(self):
        create_and_save_a_case(
            domain='enikshay-np',
            case_id=self.patient_detail.PregId.strip(),
            case_name=self.patient_detail.pname,
            # if can be blank (or null) should we skip adding the property?
            case_properties={
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
            case_type='person',
        )

    def create_occurrence_cases(self):
        for outcome in Outcome.objects.filter(PatientId=self.patient_detail):
            create_and_save_a_case(
                domain='enikshay-np',
                case_id=make_uuid(),
                case_name=make_uuid(),
                case_properties={
                    'nikshay_id': outcome.PatientId.PregId,
                },
                case_type='occurrence',
            )

class Command(BaseCommand):

    def handle(self, *args, **options):
        counter = 0
        for patient_detail in PatientDetail.objects.all():
            case_factory = CaseFactory(patient_detail)
            case_factory.create_cases()
            counter += 1
            print counter
        print 'All patient cases created'
