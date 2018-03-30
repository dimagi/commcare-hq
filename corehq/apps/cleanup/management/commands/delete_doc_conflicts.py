from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from couchdbkit.exceptions import BulkSaveError
from corehq.util.couch import categorize_bulk_save_errors
from dimagi.utils.couch.database import get_db
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def bulk_delete(db, docs):
    if not docs:
        return

    logger.info("Deleting {} doc revisions".format(len(docs)))
    try:
        db.bulk_delete(docs)
    except BulkSaveError as e:
        errors = categorize_bulk_save_errors(e)
        successes = errors.pop(None, [])
        conflicts = errors.pop('conflict', [])
        logger.error("BulkSaveError: {} successful, {} conflicts".format(len(successes), len(conflicts)))
        for error, results in errors.items():
            logger.error(results)
    else:
        logger.info('{} doc revisions deleted'.format(len(docs)))


class Command(BaseCommand):
    help = 'Delete document conflicts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch_size',
            action='store',
            type=int,
            dest='batch',
            default=500,
            help="Only process this many docs.",
        )

    def handle(self, **options):
        db = get_db()
        while True:
            results = db.view('doc_conflicts/conflicts', reduce=False, limit=options['batch'], include_docs=True, conflicts=True)
            total = results.total_rows
            if not total:
                logger.info('Document conflict deletion complete')
                return
            logger.info('Processing {} of {} docs'.format(len(results), total))
            to_delete = []
            for row in results:
                doc = row['doc']
                conflicts = doc.get('_conflicts', [])
                doc_id = doc['_id']
                logger.info('Deleting {} conflicts for doc: {}'.format(len(conflicts), doc_id))
                for rev in conflicts:
                    to_delete.append({
                        '_id': doc_id,
                        '_rev': rev
                    })
                    if len(to_delete) > 100:
                        bulk_delete(db, to_delete)
                        to_delete = []

            bulk_delete(db, to_delete)
