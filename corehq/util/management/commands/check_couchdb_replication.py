from __future__ import absolute_import

import base64
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.util.couchdb_management import couch_config


class Command(BaseCommand):
    help = "Check status or cancel replication"

    def add_arguments(self, parser):
        parser.add_argument('replication_id')
        parser.add_argument('--cancel', action='store_true')

    def handle(self, replication_id, cancel, **options):
        replicator = couch_config.get_db(None).server['_replicator']
        replication_doc = replicator.get(replication_id)
        if cancel:
            response = replicator.delete_doc(replication_doc)
            if response['ok']:
                print('Replication cancelled')
            else:
                print(json.dumps(response, indent=4))
        else:
            print(json.dumps(replication_doc, indent=4))
