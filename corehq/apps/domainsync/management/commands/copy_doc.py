from __future__ import print_function
import os
from couchdbkit import Database
from dimagi.utils.couch.database import get_db
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.domainsync.config import DocumentTransform, save


class Command(BaseCommand):
    help = ("Copy couch docs given as comma-separated list of IDs or path to file containing one ID per line. "
            "If domain is supplied save the doc with the given domain instead of its original domain.")
    args = '<sourcedb> <doc_ids_or_file_path> (<domain>)'
    label = ""

    def handle(self, *args, **options):
        if len(args) < 2 or len(args) > 3:
            raise CommandError('Usage is copy_doc %s' % self.args)

        sourcedb = Database(args[0])
        doc_ids_or_file = args[1]
        domain = args[2] if len(args) == 3 else None

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
