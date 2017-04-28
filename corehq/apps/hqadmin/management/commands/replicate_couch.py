from django.core.management import BaseCommand
from django.conf import settings
from couchdbkit.client import Server
from couchforms.models import XFormInstance


class Command(BaseCommand):
    """
    Example: ./manage.py couch_replicate replicate_couch

    """
    def add_arguments(self, parser):
        parser.add_argument(
            '--db',
            action='store',
            default=None,
            help="Pass in the database you want to migrate",
        )

        parser.add_argument(
            '--all',
            action='store_true',
            default=None,
            help="Pass in the database you want to migrate",
        )

    def handle(self, db=None, all=False, **kwargs):
        couch_server = XFormInstance.get_db().server

        for db in couch_server.all_dbs():
            if db not in {'_user', '_replicator'}:
                source = '{}/{}'.format(couch_server.uri, db)
                target = 'DESTINATION_URI/{}'.format(db)
                couch_server.replicate(
                    source,
                    target
                )
