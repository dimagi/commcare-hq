from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import os
from couchdbkit import Database
from dimagi.utils.couch.database import get_db
from django.core.management.base import BaseCommand
from corehq.apps.domainsync.config import DocumentTransform, save


class Command(BaseCommand):
    help = ("Copy couch docs given as comma-separated list of IDs or path to file containing one ID per line. "
            "If domain is supplied save the doc with the given domain instead of its original domain.")
    label = ""

    def add_arguments(self, parser):
        parser.add_argument(
            'sourcedb',
        )
        parser.add_argument(
            'doc_ids_or_file',
        )
        parser.add_argument(
            'domain',
            nargs='?',
        )

    def handle(self, sourcedb, doc_ids_or_file, domain, **options):
        sourcedb = Database(sourcedb)

        if os.path.isfile(doc_ids_or_file):
            with open(doc_ids_or_file) as f:
                doc_ids = f.read().splitlines()
        else:
            doc_ids = doc_ids_or_file.split(',')

        print("Starting copy of {} docs".format(len(doc_ids)))
        for doc_id in doc_ids:
            print('Copying doc: {}'.format(doc_id))
            doc_json = sourcedb.get(doc_id)
            if domain:
                doc_json['domain'] = domain
            dt = DocumentTransform(doc_json, sourcedb)
            save(dt, get_db())
