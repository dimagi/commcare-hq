from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json

from corehq.util.couch import IterDB
from corehq.util.log import with_progress_bar
from couchforms.const import DEVICE_LOG_XMLNS
from dimagi.utils.couch.database import iter_docs_with_retry
from django.core.management import BaseCommand
from couchforms.models import XFormInstance


class Command(BaseCommand):
    filename = 'device_log_docs_to_delete'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dump',
            action='store_true',
            default=False,
            help='Dump all device log docs to a file named device_log_docs_to_delete',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            default=False,
            help='Read docs from a file named device_log_docs_to_delete and delete them',
        )

    def handle(self, **options):
        if options.get('dump'):
            self.dump_to_file()
        if options.get('delete'):
            self.delete_from_file()

    def dump_to_file(self):
        try:
            doc_count = XFormInstance.get_db().view(
                'couchforms/by_xmlns',
                key=DEVICE_LOG_XMLNS,
                reduce=True,
            ).one()['value']
        except TypeError:
            doc_count = 0

        device_log_ids = [row['id'] for row in XFormInstance.get_db().view(
            'couchforms/by_xmlns',
            key=DEVICE_LOG_XMLNS,
            reduce=False,
        )]

        with open(self.filename, 'w') as f:
            device_log_docs = iter_docs_with_retry(XFormInstance.get_db(), device_log_ids)
            for doc in with_progress_bar(device_log_docs, length=doc_count):
                f.write(json.dumps(doc) + '\n')

    def delete_from_file(self):
        with open(self.filename) as f:
            doc_count = sum(1 for line in f)
        with open(self.filename) as f:
            with IterDB(XFormInstance.get_db(), throttle_secs=2, chunksize=100) as iter_db:
                for line in with_progress_bar(f, length=doc_count):
                    doc = json.loads(line)
                    assert doc['xmlns'] == DEVICE_LOG_XMLNS
                    assert doc['doc_type'] == 'XFormInstance'
                    iter_db.delete(doc)
        if iter_db.errors_by_type:
            print('There were some errors', iter_db.errors_by_type)
