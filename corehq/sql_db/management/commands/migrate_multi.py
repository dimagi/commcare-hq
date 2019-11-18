from copy import copy
import sys

import gevent
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from corehq.util.log import get_traceback_string


class Command(BaseCommand):
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

    def handle(self, app_label, migration_name, **options):
        args = []
        if app_label is not None:
            args.append(app_label)
        if migration_name is not None:
            args.append(migration_name)

        options['verbosity'] = 0

        def migrate_db(db_alias, options=options):
            call_options = copy(options)
            call_options['database'] = db_alias
            call_command(
                'migrate',
                *args,
                **call_options
            )

        dbs_to_migrate = [
            db_alias
            for db_alias in settings.DATABASES.keys()
            if settings.DATABASES[db_alias].get('MIGRATE', True)
        ]
        dbs_to_skip = list(set(settings.DATABASES) - set(dbs_to_migrate))

        print('\nThe following databases will be migrated:\n * {}\n'.format('\n * '.join(dbs_to_migrate)))
        if dbs_to_skip:
            print('\nThe following databases will be skipped:\n * {}\n'.format('\n * '.join(dbs_to_skip)))

        jobs = [
            gevent.spawn(migrate_db, db_alias)
            for db_alias in dbs_to_migrate
        ]

        gevent.joinall(jobs)

        migration_error_occured = False
        for job in jobs:
            try:
                job.get()
            except Exception:
                print('\n======================= Error During Migration =======================')
                print(get_traceback_string())
                migration_error_occured = True

        if migration_error_occured:
            sys.exit(1)
