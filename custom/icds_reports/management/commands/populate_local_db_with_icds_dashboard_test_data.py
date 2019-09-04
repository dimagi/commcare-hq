
from django.core.management.base import BaseCommand
from psycopg2._psycopg import IntegrityError

from custom.icds_reports import tests as icds_tests


class Command(BaseCommand):
    help = "Populates your local database with test data for the dashboard."

    def handle(self, *args, **options):
        proceed_str = input(
            '=================================================\n'
            'This command deletes a lot of things, including: \n'
            ' - ALL local location information\n'
            ' - ALL local ICDS UCR data\n\n'
            'Are you sure you want to proceed? (y/N)\n')
        if proceed_str.lower().strip() == 'y':
            try:
                icds_tests.setUpModule()
            except IntegrityError:
                print(
                    '=================================================\n'
                    'It looks like your existing data conflicted with setup. \n'
                    'You may need to manually delete some data from tables.\n'
                    '=================================================\n'
                )
                raise
        else:
            print('operation canceled')
