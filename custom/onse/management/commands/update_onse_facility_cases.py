from django.core.management import BaseCommand

from custom.onse.tasks import update_facility_cases_from_dhis2_data_elements


class Command(BaseCommand):
    help = ('Update facility_supervision cases with indicators collected '
            'in DHIS2 over the last quarter.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            help=('The period of data to import. e.g. "2020Q1". '
                  'Defaults to last quarter.'),
        )

    def handle(self, *args, **options):
        update_facility_cases_from_dhis2_data_elements.apply(kwargs={
            'period': options.get('period'),
            'print_notifications': True,
        })
