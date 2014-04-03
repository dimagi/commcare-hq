from django.core.management.base import LabelCommand

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.chunked import chunked

from corehq.apps.groups.models import Group


class Command(LabelCommand):

    def handle(self, *args, **options):
        db = Group.get_db()

        def get_doc_ids():
            for result in db.view(
                    'groups/all_groups',
                    reduce=False):
                yield result['id']

        CHUNK_SIZE = 100
        for i, docs in enumerate(chunked(iter_docs(db, get_doc_ids()), CHUNK_SIZE)):
            print i * CHUNK_SIZE
            db.bulk_save([Group.wrap(doc) for doc in docs])
