from django.core.management import BaseCommand

from custom.enikshay.nikshay_datamigration.models import PatientDetail


class Command(BaseCommand):

    def handle(self, *args, **options):
        counter = 0
        for patient_detail in PatientDetail.objects.all():
            patient_detail.create_person_case()
            counter += 1
            print counter
        print 'All patient cases created'
