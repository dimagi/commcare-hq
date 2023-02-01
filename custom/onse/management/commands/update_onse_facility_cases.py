import sys

from django.core.management import BaseCommand

from custom.onse.tasks import (
    check_server_status,
    execute_update_facility_cases_from_dhis2_data_elements,
    get_dhis2_server,
)


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
        period = options.get('period')
        print_notifications = True
        dhis2_server = get_dhis2_server(print_notifications)

        server_status = check_server_status(dhis2_server)
        if server_status['error']:
            print(str(server_status['error']), file=sys.stderr)
            sys.exit(1)

        execute_update_facility_cases_from_dhis2_data_elements(
            dhis2_server,
            period,
            print_notifications,
        )
