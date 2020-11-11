from django.core.management import BaseCommand

from custom.onse.tasks import update_facility_cases_from_dhis2_data_elements


class Command(BaseCommand):
    help = ('Update facility_supervision cases with indicators collected '
            'in DHIS2 over the last quarter.')

    def handle(self, *args, **options):
        update_facility_cases_from_dhis2_data_elements.apply(kwargs={
            'print_notifications': True})
