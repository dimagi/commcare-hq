
import csv342 as csv
import datetime

from django.core.management.base import BaseCommand

from corehq.util.couch import IterDB
from corehq.util.log import with_progress_bar
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    help = ("Save a bunch of couch documents so they are re-sent to kafka. "
            "Pass in a file with one doc id per line")

    def add_arguments(self, parser):
        parser.add_argument('ids_file')

    def handle(self, ids_file, **options):
        with open(ids_file, encoding='utf-8') as f:
            doc_ids = [line.strip() for line in f]
        total_doc_ids = len(doc_ids)
        doc_ids = set(doc_ids)
        print("{} total doc ids, {} unique".format(total_doc_ids, len(doc_ids)))

        db = XFormInstance.get_db()  # Both forms and cases are in here
        with IterDB(db) as iter_db:
            for doc in iter_docs(db, with_progress_bar(doc_ids)):
                iter_db.save(doc)

        print("{} docs saved".format(len(iter_db.saved_ids)))
        print("{} docs errored".format(len(iter_db.error_ids)))
        not_found = len(doc_ids) - len(iter_db.saved_ids) - len(iter_db.error_ids)
        print("{} docs not found".format(not_found))

        filename = '{}_{}.csv'.format(ids_file.split('/')[-1],
                                      datetime.datetime.now().isoformat())
        with open(filename, 'w', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['doc_id', 'status'])
            for doc_id in doc_ids:
                if doc_id in iter_db.saved_ids:
                    status = "saved"
                elif doc_id in iter_db.error_ids:
                    status = "errored"
                else:
                    status = "not_found"
                writer.writerow([doc_id, status])

        print("Saved results to {}".format(filename))
