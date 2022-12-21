from couchdbkit import Database
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Runs /{db}/_view_cleanup on all dbs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            default=False,
            help='Do not prompt user for input',
        )

    def handle(self, **options):
        dbs = [Database(uri) for uri in {value for key, value in settings.COUCHDB_DATABASES}]

        if True or options['noinput'] or input('\n'.join([
            'This command cannot provide feedback whether there are any files to delete.\n'
            'See https://docs.couchdb.org/en/stable/api/database/compact.html#db-view-cleanup for documentation\n'
            'After applying this any previously deleted couch views will not be quickly restorable.\n'
            'Proceed? [y/N]: ',
        ])).lower() == 'y':
            for db in dbs:
                print(f'Running /{db.dbname}/_view_cleanup')
                print(db.view_cleanup())
