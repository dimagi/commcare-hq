from __future__ import print_function
from copy import copy
from optparse import make_option

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    args = ''
    help = "Call 'migrate' for each configured database"

    def add_arguments(self, parser):
        parser.add_argument('app_label', nargs='?',
            help='App label of an application to synchronize the state.')
        parser.add_argument('migration_name', nargs='?',
            help=(
                'Database state will be brought to the state after that '
                'migration. Use the name "zero" to unapply all migrations.'
            ),
        )
        parser.add_argument('--noinput', action='store_false', dest='interactive', default=True,
            help='Tells Django to NOT prompt the user for input of any kind.')
        parser.add_argument('--fake', action='store_true', dest='fake', default=False,
            help='Mark migrations as run without actually running them.')
        parser.add_argument('--list', '-l', action='store_true', dest='list', default=False,
            help='Show a list of all known migrations and which are applied.')

    def handle(self, *args, **options):
        for db_alias in settings.DATABASES.keys():
            print('\n======================= Migrating DB: {} ======================='.format(db_alias))
            call_options = copy(options)
            call_options['database'] = db_alias
            call_command(
                'migrate',
                *args,
                **call_options
            )
