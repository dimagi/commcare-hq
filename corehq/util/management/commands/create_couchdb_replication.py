import json

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from corehq.util.couchdb_management import couch_config


def _check_db_name(dbname):
    if not dbname.startswith('commcarehq__'):
        dbname = 'commcarehq__{}'.format(dbname)
    return dbname


class Command(BaseCommand):
    help = "Set up replication between two databases (on the CommCare HQ CouchDB cluster)"

    def add_arguments(self, parser):
        parser.add_argument('sourcedb')
        parser.add_argument('targetdb')
        parser.add_argument('--filter', help='Document filter to use e.g. "not_deleted/filter"')
        parser.add_argument('--continuous', default=True, action='store_true')
        parser.add_argument('--createtarget', default=False, action='store_true',
                            help='Use this flag it the target DB does not already exist.')

    def handle(self, sourcedb, targetdb, **options):
        filter = options.get('filter')
        continuous = options.get('continuous')
        createtarget = options.get('createtarget')

        server = couch_config.get_db(None).server

        params = {
            'continuous': continuous
        }

        if createtarget:
            params['create_target'] = True

        if filter:
            params['filter'] = filter

        source = _check_db_name(sourcedb)
        target = _check_db_name(targetdb)
        response = server.replicate(source, target, **params)
        if not response['ok']:
            raise CommandError(json.dumps(response))

        local_id = response['_local_id']
        print('\nReplication created: {}'.format(local_id))
        print("\nUseful commands  :")
        print("   Check status  : python manage.py check_couchdb_replication {}".format(local_id))
        print("   Cancel        : python manage.py check_couchdb_replication {} --cancel\n".format(local_id))
