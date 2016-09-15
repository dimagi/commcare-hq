from django.core.management import BaseCommand

from corehq.util.test_utils import create_and_save_a_case

from custom.enikshay.nikshay_datamigration.models import PatientDetail


class CaseFactory(object):

    patient_detail = None

    def __init__(self, patient_detail):
        self.patient_detail = patient_detail

    def create_cases(self):
        self.create_person_case()

    def create_person_case(self):
        create_and_save_a_case(
            domain='enikshay-np',
            case_id=self.patient_detail.PregId.strip(),
            case_name=self.patient_detail.pname,
            # if can be blank (or null) should we skip adding the property?
            case_properties={
                'name': self.patient_detail.name,
                'aadhaar_number': self.patient_detail.aadhaar_number,
                'phi': self.patient_detail.phi,
                'first_name': self.patient_detail.first_name,
                'middle_name': self.patient_detail.middle_name,
                'last_name': self.patient_detail.last_name,
                'age': self.patient_detail.age,
                'sex': self.patient_detail.sex,
                'current_address': self.patient_detail.current_address,
                'mobile_number': self.patient_detail.mobile_number,
            }
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
