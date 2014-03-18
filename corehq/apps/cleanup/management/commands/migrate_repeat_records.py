from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from corehq import Domain
from corehq.apps.receiverwrapper.models import RepeatRecord
from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    """
    Migrates RepeatRecord docs in a domain from the old db to the new db.
    """

    def handle(self, *args, **options):
        domain = args[0]
        old_db = Domain.get_db()
        new_db = RepeatRecord.get_db()
        assert old_db.dbname != new_db.dbname
        doc_ids = [r['id'] for r in old_db.view('domain/docs',
            startkey=[domain, 'RepeatRecord'],
            endkey=[domain, 'RepeatRecord', {}],
            reduce=False,
        )]
        count = len(doc_ids)
        chunksize = 250

        for i, docs in enumerate(chunked(iter_docs(old_db, doc_ids, chunksize), chunksize)):
            for doc in docs:
                if '_rev' in doc:
                    del doc['_rev']
            new_db.bulk_save(docs, new_edits=False)
            print 'checked %s / %s' % (i * chunksize, count)
