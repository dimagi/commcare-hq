
from django.core.management.base import BaseCommand, CommandError
from psycopg2._psycopg import IntegrityError

import settings
from custom.icds_reports.tests import agg_tests


class Command(BaseCommand):
    help = "Populates your local database with test data for the dashboard."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("This command is only allowed in DEBUG mode to prevent accidental data deletion")

        proceed_str = input(
            '=================================================\n'
            'This command deletes a lot of things, including: \n'
            ' - ALL local location information\n'
            ' - ALL local ICDS UCR data\n\n'
            'Are you sure you want to proceed? (y/N)\n')
        if proceed_str.lower().strip() == 'y':
            try:
                agg_tests.setUpModule()
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
