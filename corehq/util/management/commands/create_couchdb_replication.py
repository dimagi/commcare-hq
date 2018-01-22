from __future__ import absolute_import

import base64
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.util.couchdb_management import couch_config


def _make_db_url(dbname, port):
    if not dbname.startswith('commcarehq__'):
        dbname = 'commcarehq__{}'.format(dbname)
    uri = couch_config.get_db(None).server[dbname].uri
    proxy_port = settings.COUCH_DATABASES['default']['COUCH_SERVER_ROOT'].split(':')[1]
    if port != proxy_port:
        uri = uri.replace(proxy_port, port)
    return '{}'.format(uri)


class Command(BaseCommand):
    help = "Set up replication between two databases (on the CommCare HQ CouchDB cluster)"

    def add_arguments(self, parser):
        parser.add_argument('sourcedb')
        parser.add_argument('targetdb')
        parser.add_argument('--couchdbport', default='15984', help='Node port number for couchdb')
        parser.add_argument('--filter', help='Document filter to use e.g. "not_deleted/filter"')
        parser.add_argument('--continuous', default=True, action='store_true')
        parser.add_argument('--createtarget', default=False, action='store_true',
                            help='Use this flag it the target DB does not already exist.')

    def handle(self, sourcedb, targetdb, **options):
        filter = options.get('filter')
        continuous = options.get('continuous')
        createtarget = options.get('createtarget')
        couchdbport = options.get('couchdbport')

        replicator_db = couch_config.get_db(None).server['_replicator']

        replication_doc = {
            'source': {
                'url': _make_db_url(sourcedb, couchdbport)
            },
            'target': {
                'url': _make_db_url(targetdb, couchdbport)
            },
            'use_checkpoints': True,
            'continuous': continuous
        }

        if createtarget:
            replication_doc['create_target'] = True

            # Check for admin party
            if settings.COUCH_DATABASES['default']['COUCH_USERNAME']:
                auth_header = base64.b32encode('{COUCH_USERNAME}:{COUCH_PASSWORD}'.format(
                    **settings.COUCH_DATABASES['default']
                ))
                headers = {
                    'Authorization': 'Basic {}'.format(auth_header)
                }
                replication_doc['source']['headers'] = headers
                replication_doc['target']['headers'] = headers

        if filter:
            replication_doc['filter'] = filter

        doc_id = replicator_db.save_doc(replication_doc)['id']
        replication_doc = replicator_db.get(doc_id)
        print(json.dumps(replication_doc, indent=4))
        print("\n\n")
        print("Useful commands  :")
        print("   Check status  : python manage.py check_couchdb_replication {}".format(doc_id))
        print("   Cancel        : python manage.py check_couchdb_replication {} --cancel\n".format(doc_id))
